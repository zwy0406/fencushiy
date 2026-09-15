import math
import random

import numpy as np

from models.infer_models import OnlineModelSuite
from phy.large_scale_fading import general_path_loss
from topology.mwmp_dca.cluster_metrics import ClusterMetrics
from topology.mwmp_dca.cluster_rotation import ClusterRotationManager
from topology.mwmp_dca.predictor import build_predictor
from topology.mwmp_dca.recent_baselines import (
    TdcMopsoSelector,
    mdcs_candidate_score,
    select_mdcs_heads,
    tdc_candidate_score,
)
from topology.mwmp_dca.trajectory_let_calculator import trajectory_based_let
from topology.mwmp_dca.weight_calculator import WeightCalculator, clamp01
from utils import config
from utils.util_function import euclidean_distance_3d


class ClusterManager:
    def __init__(self, simulator):
        self.simulator = simulator
        self.env = simulator.env
        self.model_suite = OnlineModelSuite()
        self.model_suite.refresh_status()
        self.requested_algorithm = config.CLUSTER_ALGORITHM
        self._maybe_downgrade_ga_mode()
        self.predictor = build_predictor()
        self.weight_calculator = WeightCalculator()
        self.rotation_manager = ClusterRotationManager()
        self.metrics = ClusterMetrics()
        self.rng = random.Random(simulator.seed + 101)
        self.cluster_snapshot = {}
        self.round_counter = 0
        self.stable_rounds = 0
        self.better_candidate_persistence = {}
        self.smoothed_tlet = {}
        self.backbone_relay_hold_until = {}
        self.env.process(self.run())

    def _maybe_downgrade_ga_mode(self):
        if config.CLUSTER_ALGORITHM.upper() != 'GA_MP_DCA':
            config.MODEL_STATUS['ga_mode'] = 'not_requested'
            return

        lstm_missing = config.USE_LSTM_PREDICTOR and config.PREDICTOR_MODE.lower() == 'lstm' and not self.model_suite.trajectory_model.available
        gat_missing = config.USE_GAT_FEATURE and not self.model_suite.graph_model.available
        if lstm_missing or gat_missing:
            config.MODEL_STATUS['ga_mode'] = 'downgraded_to_mwmp'
            config.CLUSTER_ALGORITHM = 'MWMP_DCA'
            config.USE_GAT_FEATURE = False
            if lstm_missing:
                config.USE_LSTM_PREDICTOR = False
                config.PREDICTOR_MODE = 'kinematic'
        else:
            config.MODEL_STATUS['ga_mode'] = 'active'

    def active_drones(self):
        return [drone for drone in self.simulator.drones if not getattr(drone, 'is_base_station', False)]

    def run(self):
        while True:
            yield self.env.timeout(config.CLUSTER_INTERVAL)
            self.recluster()

    def recluster(self):
        self.round_counter += 1
        drones = self.active_drones()
        if not drones:
            return

        previous_head_ids = {drone.identifier for drone in drones if getattr(drone, 'cluster_role', None) == 'CH'}
        predictions = {drone.identifier: self.predictor.predict(drone, config.PREDICTION_HORIZON) for drone in drones}
        neighbor_map = self._build_neighbor_map(drones)
        raw_tlets = {
            drone.identifier: self._average_local_tlet(
                drone,
                neighbor_map.get(drone.identifier, []),
                predictions,
            )
            for drone in drones
        }
        tlets = self._smooth_tlets(raw_tlets)
        feature_rows, adjacency, degree_scores = self._build_graph_inputs(drones, neighbor_map)
        topology_scores, topology_embeddings = self._compute_topology_scores(drones, feature_rows, adjacency, degree_scores)
        scores = {}

        for drone in drones:
            scores[drone.identifier] = self._score_drone(
                drone=drone,
                neighbors=neighbor_map.get(drone.identifier, []),
                predictions=predictions,
                topology_score=topology_scores.get(drone.identifier, degree_scores.get(drone.identifier, 0.0)),
                tlet=tlets.get(drone.identifier, 0.0),
            )
            drone.cluster_weight = scores[drone.identifier]
            drone.topology_score = topology_scores.get(drone.identifier, degree_scores.get(drone.identifier, 0.0))
            drone.graph_embedding = topology_embeddings.get(drone.identifier, [])
            drone.raw_avg_let = raw_tlets.get(drone.identifier, 0.0)
            drone.avg_let = tlets.get(drone.identifier, 0.0)
            drone.local_density = len(neighbor_map.get(drone.identifier, []))
            drone.avg_link_quality = self._average_link_quality(drone, neighbor_map.get(drone.identifier, []))
            drone.mobility_factor = self._mobility_factor(drone, predictions[drone.identifier])
            self.metrics.record_topology_score(drone.topology_score)

        if config.CLUSTER_ALGORITHM.upper() == 'GA_MP_DCA' and config.GA_CH_PERSISTENCE_BONUS > 0:
            for head_id in previous_head_ids:
                if head_id in scores:
                    scores[head_id] = clamp01(scores[head_id] + config.GA_CH_PERSISTENCE_BONUS)
                    self.simulator.drones[head_id].cluster_weight = scores[head_id]

        for drone in drones:
            drone.cluster_role = 'CM'
            drone.is_backbone_connector = False
            drone.cluster_id = None
            drone.cluster_head = None
            drone.cluster_members = []

        for drone in drones:
            self.metrics.record_prediction_error(self.predictor.evaluate_recent(drone, config.PREDICTION_HORIZON))

        candidate_heads, suppressed_count, backoff_map = self._elect_cluster_heads(
            drones,
            neighbor_map,
            scores,
            previous_head_ids,
        )

        if not candidate_heads:
            candidate_heads = [max(drones, key=lambda d: scores[d.identifier])]

        candidate_heads = sorted(
            candidate_heads,
            key=lambda d: (scores[d.identifier], d.residual_energy, -d.identifier),
            reverse=True,
        )
        if config.USE_CH_ROTATION and config.CLUSTER_ALGORITHM.upper() in ('MWMP_DCA', 'GA_MP_DCA'):
            candidate_heads = self._apply_rotation(candidate_heads, drones, neighbor_map, scores, previous_head_ids)

        clusters = []
        for head in candidate_heads:
            head.cluster_role = 'CH'
            head.cluster_head = head
            head.cluster_id = head.identifier
            head.cluster_members = [head.identifier]
            head.cluster_weight = scores[head.identifier]
            head.cluster_age = getattr(head, 'cluster_age', 0) + 1 if head.identifier in previous_head_ids else 1

        extra_heads = []
        for drone in drones:
            if drone.cluster_role == 'CH':
                continue
            reachable_heads = [
                head for head in candidate_heads
                if euclidean_distance_3d(drone.coords, head.coords) <= config.COMMUNICATION_RANGE
            ]
            if not reachable_heads:
                extra_heads.append(drone)

        for head in extra_heads:
            head.cluster_role = 'CH'
            head.cluster_head = head
            head.cluster_id = head.identifier
            head.cluster_members = [head.identifier]
            head.cluster_weight = scores[head.identifier]
            head.cluster_age = getattr(head, 'cluster_age', 0) + 1 if head.identifier in previous_head_ids else 1
            candidate_heads.append(head)

        backbone_nodes = self._connect_backbone(
            candidate_heads,
            drones,
            scores,
            previous_head_ids,
        )
        known_head_ids = {head.identifier for head in candidate_heads}
        connectors = [
            drone for drone in backbone_nodes
            if drone.identifier not in known_head_ids
        ]
        hold_rounds = max(0, int(getattr(config, 'BACKBONE_RELAY_HOLD_ROUNDS', 0)))
        if hold_rounds:
            active_ids = {drone.identifier for drone in drones}
            self.backbone_relay_hold_until = {
                node_id: until_round
                for node_id, until_round in self.backbone_relay_hold_until.items()
                if until_round >= self.round_counter and node_id in active_ids
            }
            for connector in connectors:
                self.backbone_relay_hold_until[connector.identifier] = (
                    self.round_counter + hold_rounds
                )
            by_id = {drone.identifier: drone for drone in drones}
            backbone_ids = {drone.identifier for drone in backbone_nodes}
            for node_id in sorted(self.backbone_relay_hold_until):
                if node_id in known_head_ids or node_id in backbone_ids:
                    continue
                held = by_id.get(node_id)
                if held is not None:
                    backbone_nodes.append(held)
                    backbone_ids.add(node_id)
            connectors = [
                drone for drone in backbone_nodes
                if drone.identifier not in known_head_ids
            ]
        for connector in connectors:
            connector.is_backbone_connector = True

        for drone in drones:
            if drone.cluster_role == 'CH':
                continue
            reachable_heads = [head for head in candidate_heads if euclidean_distance_3d(drone.coords, head.coords) <= config.COMMUNICATION_RANGE]
            if reachable_heads:
                best_head = max(
                    reachable_heads,
                    key=lambda head: (scores[head.identifier], self._pair_link_quality(drone, head), -euclidean_distance_3d(drone.coords, head.coords)),
                )
            else:
                drone.cluster_role = 'CH'
                drone.cluster_head = drone
                drone.cluster_id = drone.identifier
                drone.cluster_members = [drone.identifier]
                drone.cluster_weight = scores[drone.identifier]
                if all(head.identifier != drone.identifier for head in candidate_heads):
                    candidate_heads.append(drone)
                    backbone_nodes.append(drone)
                continue
            drone.cluster_role = 'CM'
            drone.cluster_head = best_head
            drone.cluster_id = best_head.identifier
            if drone.identifier not in best_head.cluster_members:
                best_head.cluster_members.append(drone.identifier)

        join_count = sum(max(0, len(head.cluster_members) - 1) for head in candidate_heads)
        formation_time = max(backoff_map.values()) if backoff_map else 0.0
        self.metrics.record_control_exchange(
            announces=len(candidate_heads),
            joins=join_count,
            suppressed=suppressed_count,
        )
        self.metrics.record_election_round(
            round_counter=self.round_counter,
            candidate_ids=[drone.identifier for drone in drones],
            winner_ids=[head.identifier for head in candidate_heads],
            suppressed=suppressed_count,
            formation_time_us=formation_time,
            backoff_map=backoff_map,
        )

        for head in candidate_heads:
            clusters.append((head.identifier, head.cluster_members[:]))

        for drone in drones:
            if drone.cluster_role != 'CH':
                drone.cluster_age = 0

        (
            backbone_connectivity,
            bs_reachability,
            path_preservation,
            bs_reachability_efficiency,
        ) = self._backbone_connectivity(backbone_nodes)
        self.metrics.record_backbone_connectivity(
            backbone_connectivity,
            bs_reachability,
            path_preservation,
            bs_reachability_efficiency,
        )

        new_snapshot = {drone.identifier: drone.cluster_id for drone in drones}
        if self.cluster_snapshot and new_snapshot == self.cluster_snapshot:
            self.stable_rounds += 1
        else:
            self.stable_rounds = 0
            self.metrics.record_reclustering()
        self.cluster_snapshot = new_snapshot
        self.metrics.record_cluster_snapshot(clusters, self.round_counter)

        control_overhead = len(candidate_heads) + join_count
        self.simulator.metrics.increment_control_packets(control_overhead, category='cluster')

        head_tlets = [drone.avg_let for drone in drones if drone.cluster_role == 'CH']
        if head_tlets:
            self.metrics.record_average_tlet(sum(head_tlets) / len(head_tlets))

        for drone in self.simulator.drones:
            if hasattr(drone, 'routing_protocol') and drone.routing_protocol is not None:
                update_role = getattr(drone.routing_protocol, 'update_role', None)
                if callable(update_role):
                    update_role(
                        'BR' if getattr(drone, 'is_backbone_connector', False)
                        else drone.cluster_role
                    )

    def _build_neighbor_map(self, drones):
        neighbor_map = {}
        for drone in drones:
            neighbors = []
            for candidate in drones:
                if candidate.identifier == drone.identifier:
                    continue
                if euclidean_distance_3d(drone.coords, candidate.coords) <= config.COMMUNICATION_RANGE:
                    neighbors.append(candidate)
            neighbor_map[drone.identifier] = neighbors
        return neighbor_map

    def _build_graph_inputs(self, drones, neighbor_map):
        feature_rows = []
        adjacency = np.eye(len(drones), dtype=np.float32)
        degree_scores = {}

        for row_idx, drone in enumerate(drones):
            neighbors = neighbor_map.get(drone.identifier, [])
            degree_ratio = clamp01(len(neighbors) / max(1, len(drones) - 1))
            degree_scores[drone.identifier] = degree_ratio
            link_quality = self._average_link_quality(drone, neighbors)
            speed_ratio = clamp01(sum(value ** 2 for value in drone.velocity) ** 0.5 / max(1.0, config.DEFAULT_UAV_SPEED * 2))
            feature_rows.append([
                clamp01(drone.residual_energy / float(config.INITIAL_ENERGY)),
                link_quality,
                degree_ratio,
                speed_ratio,
            ])
            for col_idx, candidate in enumerate(drones):
                if row_idx == col_idx:
                    continue
                if candidate in neighbors:
                    adjacency[row_idx, col_idx] = 1.0
        return feature_rows, adjacency, degree_scores

    def _compute_topology_scores(self, drones, feature_rows, adjacency, degree_scores):
        algorithm = config.CLUSTER_ALGORITHM.upper()
        heuristic_scores = {drone.identifier: degree_scores.get(drone.identifier, 0.0) for drone in drones}
        embeddings = {drone.identifier: [] for drone in drones}

        if algorithm != 'GA_MP_DCA':
            return heuristic_scores, embeddings

        if not config.USE_GAT_FEATURE:
            config.MODEL_STATUS['gat'] = 'ablation_disabled'
            return heuristic_scores, embeddings

        scores, raw_embeddings = self.model_suite.graph_model.encode(feature_rows, adjacency)
        if scores is None:
            status = getattr(self.model_suite.graph_model, 'status', 'unavailable')
            config.MODEL_STATUS['gat'] = f'fallback:{status}'
            return heuristic_scores, embeddings

        result_scores = {}
        for idx, drone in enumerate(drones):
            result_scores[drone.identifier] = clamp01(float(scores[idx]))
            embeddings[drone.identifier] = [float(value) for value in raw_embeddings[idx]]
        config.MODEL_STATUS['gat'] = getattr(self.model_suite.graph_model, 'status', 'loaded')
        return result_scores, embeddings

    def _score_drone(self, drone, neighbors, predictions, topology_score=0.0, tlet=None):
        algorithm = config.CLUSTER_ALGORITHM.upper()
        energy_ratio = clamp01(drone.residual_energy / float(config.INITIAL_ENERGY))
        density = clamp01(len(neighbors) / max(1, len(self.simulator.drones) - 1))
        link_quality = self._average_link_quality(drone, neighbors)
        if tlet is None:
            tlet = self._average_local_tlet(drone, neighbors, predictions)
        if not config.USE_TLET:
            tlet = 0.0
        tlet_ratio = self.weight_calculator.normalize_tlet(tlet)
        mobility = self._mobility_factor(drone, predictions[drone.identifier]) if config.USE_MOBILITY_FACTOR else 0.0
        load_ratio = clamp01(len(getattr(drone, 'cluster_members', [])) / max(1, config.CH_MAX_LOAD))
        poi_ratio = self._poi_affinity(drone)
        drone.poi_affinity = poi_ratio

        factors = {
            'energy_ratio': energy_ratio,
            'link_quality': link_quality,
            'density': density,
            'tlet_ratio': tlet_ratio,
            'mobility_factor': mobility,
            'poi_affinity': poi_ratio,
            'topology_score': topology_score,
        }
        self.metrics.record_weight_factors(factors)

        if algorithm == 'GA_MP_DCA':
            return self.weight_calculator.ga_score(
                energy_ratio=energy_ratio,
                link_quality=link_quality,
                tlet_ratio=tlet_ratio,
                topology_score=topology_score,
                mobility_factor=mobility,
            )

        if algorithm == 'MLSC':
            return self._mlsc_score(drone, neighbors, link_quality, density)

        if algorithm == 'MDCS':
            return mdcs_candidate_score(
                drone,
                neighbors,
                config.COMMUNICATION_RANGE,
                config.DEFAULT_UAV_SPEED,
            )

        if algorithm == 'TDC_MOPSO':
            return tdc_candidate_score(
                drone,
                neighbors,
                config.INITIAL_ENERGY,
                config.COMMUNICATION_RANGE,
                config.DEFAULT_UAV_SPEED,
            )

        if not config.USE_HYBRID_WEIGHT:
            return energy_ratio

        return self.weight_calculator.score(
            energy_ratio=energy_ratio,
            link_quality=link_quality,
            density=density,
            tlet_ratio=tlet_ratio,
            mobility_factor=mobility,
            load_ratio=load_ratio,
            poi_ratio=poi_ratio,
        )

    def _average_link_quality(self, drone, neighbors):
        if not neighbors:
            return 0.0
        qualities = []
        for neighbor in neighbors:
            qualities.append(self._pair_link_quality(drone, neighbor))
        return sum(qualities) / len(qualities)

    def _pair_link_quality(self, drone, neighbor):
        try:
            receive_power = config.TRANSMITTING_POWER * general_path_loss(neighbor, drone)
            snr = 10 * math.log10(receive_power / config.NOISE_POWER)
            return self.weight_calculator.normalize_link_quality(snr)
        except (ValueError, ZeroDivisionError):
            distance = euclidean_distance_3d(drone.coords, neighbor.coords)
            return clamp01(1.0 - distance / float(config.COMMUNICATION_RANGE))

    def _backbone_connectivity(self, candidate_heads):
        base_stations = [
            drone for drone in self.simulator.drones
            if getattr(drone, 'is_base_station', False)
        ]
        backbone_nodes = base_stations + list(candidate_heads)
        if not backbone_nodes:
            return 1.0, 1.0, 1.0, 1.0

        adjacency = {drone.identifier: set() for drone in backbone_nodes}
        for idx, drone in enumerate(backbone_nodes):
            for other in backbone_nodes[idx + 1:]:
                if euclidean_distance_3d(drone.coords, other.coords) <= config.COMMUNICATION_RANGE:
                    adjacency[drone.identifier].add(other.identifier)
                    adjacency[other.identifier].add(drone.identifier)

        components = []
        unseen = set(adjacency)
        while unseen:
            stack = [next(iter(unseen))]
            component = set()
            while stack:
                node_id = stack.pop()
                if node_id in component:
                    continue
                component.add(node_id)
                unseen.discard(node_id)
                stack.extend(adjacency[node_id] - component)
            components.append(component)
        largest_ratio = max(len(component) for component in components) / len(backbone_nodes)
        backbone_component_by_id = {
            node_id: component_idx
            for component_idx, component in enumerate(components)
            for node_id in component
        }

        physical_nodes = list(self.simulator.drones)
        physical_adjacency = {drone.identifier: set() for drone in physical_nodes}
        for idx, drone in enumerate(physical_nodes):
            for other in physical_nodes[idx + 1:]:
                if euclidean_distance_3d(drone.coords, other.coords) <= config.COMMUNICATION_RANGE:
                    physical_adjacency[drone.identifier].add(other.identifier)
                    physical_adjacency[other.identifier].add(drone.identifier)
        physical_component_by_id = {}
        unseen = set(physical_adjacency)
        component_idx = 0
        while unseen:
            stack = [next(iter(unseen))]
            while stack:
                node_id = stack.pop()
                if node_id in physical_component_by_id:
                    continue
                physical_component_by_id[node_id] = component_idx
                unseen.discard(node_id)
                stack.extend(
                    physical_adjacency[node_id] -
                    set(physical_component_by_id)
                )
            component_idx += 1

        eligible_pairs = 0
        preserved_pairs = 0
        backbone_ids = [drone.identifier for drone in backbone_nodes]
        for idx, node_id in enumerate(backbone_ids):
            for other_id in backbone_ids[idx + 1:]:
                if physical_component_by_id.get(node_id) != physical_component_by_id.get(other_id):
                    continue
                eligible_pairs += 1
                if backbone_component_by_id.get(node_id) == backbone_component_by_id.get(other_id):
                    preserved_pairs += 1
        path_preservation = preserved_pairs / eligible_pairs if eligible_pairs else 1.0

        if not base_stations:
            return largest_ratio, largest_ratio, path_preservation, path_preservation
        reachable = set()
        stack = [drone.identifier for drone in base_stations]
        while stack:
            node_id = stack.pop()
            if node_id in reachable:
                continue
            reachable.add(node_id)
            stack.extend(adjacency[node_id] - reachable)
        head_ids = {head.identifier for head in candidate_heads}
        reachable_heads = len(reachable & head_ids)
        bs_reachability = reachable_heads / len(head_ids) if head_ids else 1.0
        bs_component_ids = {
            physical_component_by_id.get(drone.identifier) for drone in base_stations
        }
        physically_reachable_heads = sum(
            1 for head_id in head_ids
            if physical_component_by_id.get(head_id) in bs_component_ids
        )
        bs_efficiency = (
            reachable_heads / physically_reachable_heads
            if physically_reachable_heads else 1.0
        )
        return largest_ratio, bs_reachability, path_preservation, bs_efficiency

    def _connect_backbone(self, candidate_heads, drones, scores, previous_head_ids):
        if not getattr(config, 'USE_BACKBONE_CONNECTORS', False):
            return candidate_heads

        base_stations = [
            drone for drone in self.simulator.drones
            if getattr(drone, 'is_base_station', False)
        ]
        nodes = base_stations + list(drones)
        by_id = {drone.identifier: drone for drone in nodes}
        adjacency = {drone.identifier: set() for drone in nodes}
        for idx, drone in enumerate(nodes):
            for other in nodes[idx + 1:]:
                if euclidean_distance_3d(drone.coords, other.coords) <= config.COMMUNICATION_RANGE:
                    adjacency[drone.identifier].add(other.identifier)
                    adjacency[other.identifier].add(drone.identifier)

        selected_ids = {head.identifier for head in candidate_heads}
        unseen = set(adjacency)
        while unseen:
            start = next(iter(unseen))
            stack = [start]
            component = set()
            while stack:
                node_id = stack.pop()
                if node_id in component:
                    continue
                component.add(node_id)
                unseen.discard(node_id)
                stack.extend(adjacency[node_id] - component)

            component_heads = selected_ids & component
            if not component_heads:
                continue
            component_bs = {drone.identifier for drone in base_stations} & component
            if component_bs:
                connected = set(component_bs)
            else:
                anchor = max(
                    component_heads,
                    key=lambda node_id: (scores.get(node_id, 0.0), -node_id),
                )
                connected = {anchor}

            pending = sorted(
                component_heads - connected,
                key=lambda node_id: (scores.get(node_id, 0.0), -node_id),
                reverse=True,
            )
            for head_id in pending:
                path = self._shortest_backbone_path(
                    head_id,
                    connected,
                    adjacency,
                    scores,
                    previous_head_ids,
                )
                if not path:
                    continue
                connected.update(path)
                selected_ids.update(node_id for node_id in path if node_id in scores)

        return sorted(
            (by_id[node_id] for node_id in selected_ids),
            key=lambda drone: (scores.get(drone.identifier, 0.0), -drone.identifier),
            reverse=True,
        )

    def _shortest_backbone_path(self, start, targets, adjacency, scores, previous_head_ids):
        queue = [start]
        parents = {start: None}
        target = None
        while queue:
            node_id = queue.pop(0)
            if node_id in targets:
                target = node_id
                break
            neighbors = sorted(
                adjacency.get(node_id, ()),
                key=lambda candidate_id: (
                    candidate_id in previous_head_ids,
                    scores.get(candidate_id, 0.0),
                    -candidate_id,
                ),
                reverse=True,
            )
            for neighbor_id in neighbors:
                if neighbor_id in parents:
                    continue
                parents[neighbor_id] = node_id
                queue.append(neighbor_id)
        if target is None:
            return []
        path = []
        node_id = target
        while node_id is not None:
            path.append(node_id)
            node_id = parents[node_id]
        return list(reversed(path))

    def _mobility_factor(self, drone, trajectory):
        if not trajectory:
            return 0.0
        displacement = euclidean_distance_3d(drone.coords, trajectory[-1])
        return clamp01(displacement / float(config.COMMUNICATION_RANGE))

    def _average_local_tlet(self, drone, neighbors, predictions):
        if not neighbors:
            return 0.0
        my_traj = predictions[drone.identifier]
        values = []
        for neighbor in neighbors:
            neighbor_traj = predictions[neighbor.identifier]
            values.append(trajectory_based_let(my_traj, neighbor_traj, config.COMMUNICATION_RANGE))
        return sum(values) / len(values) if values else 0.0

    def _smooth_tlets(self, raw_tlets):
        alpha = clamp01(getattr(config, 'TLET_SMOOTHING_ALPHA', 1.0))
        active_ids = set(raw_tlets)
        self.smoothed_tlet = {
            drone_id: value for drone_id, value in self.smoothed_tlet.items()
            if drone_id in active_ids
        }
        result = {}
        for drone_id, raw_value in raw_tlets.items():
            previous = self.smoothed_tlet.get(drone_id, raw_value)
            smoothed = alpha * raw_value + (1.0 - alpha) * previous
            self.smoothed_tlet[drone_id] = smoothed
            result[drone_id] = smoothed
        return result

    def _poi_affinity(self, drone):
        if not config.ENABLE_POI or not getattr(self.simulator, 'pois', None):
            return 0.0
        nearby = 0
        weighted = 0.0
        for poi in self.simulator.pois:
            distance = euclidean_distance_3d(drone.coords, poi.coords)
            if distance <= config.COMMUNICATION_RANGE:
                nearby += 1
                weighted += 1.0 - distance / float(config.COMMUNICATION_RANGE)
        return clamp01(weighted / max(1, nearby)) if nearby else 0.0

    def _elect_cluster_heads(self, drones, neighbor_map, scores, previous_head_ids=None):
        algorithm = config.CLUSTER_ALGORITHM.upper()
        if algorithm == 'LOWEST_ID':
            selected = self._elect_lowest_id(drones, neighbor_map)
            return selected, 0, {}
        if algorithm == 'WCA':
            return self._elect_ranked_baseline(drones, neighbor_map, self._wca_score), 0, {}
        if algorithm == 'MOBIC':
            return self._elect_ranked_baseline(drones, neighbor_map, self._mobic_score), 0, {}
        if algorithm == 'MLSC':
            return self._elect_ranked_baseline(drones, neighbor_map, lambda drone, _: scores[drone.identifier]), 0, {}
        if algorithm == 'LEACH_UAV':
            return self._elect_leach(drones), 0, {}
        if algorithm == 'KMEANS':
            return self._elect_kmeans(drones), 0, {}
        if algorithm == 'MDCS':
            return select_mdcs_heads(
                drones,
                neighbor_map,
                config.COMMUNICATION_RANGE,
                config.DEFAULT_UAV_SPEED,
                config.CLUSTER_BACKOFF_MAX,
                self.rng,
            )
        if algorithm == 'TDC_MOPSO':
            selector = TdcMopsoSelector(
                rng=self.rng,
                swarm_size=config.TDC_MOPSO_SWARM_SIZE,
                iterations=config.TDC_MOPSO_ITERATIONS,
                archive_size=config.TDC_MOPSO_ARCHIVE_SIZE,
                inertia=config.TDC_MOPSO_INERTIA,
                cognitive=config.TDC_MOPSO_COGNITIVE,
                social=config.TDC_MOPSO_SOCIAL,
                mutation_rate=config.TDC_MOPSO_MUTATION_RATE,
            )
            selected = selector.select(
                drones=drones,
                neighbor_map=neighbor_map,
                previous_head_ids=previous_head_ids or set(),
                communication_range=config.COMMUNICATION_RANGE,
                reference_speed=config.DEFAULT_UAV_SPEED,
                initial_energy=config.INITIAL_ENERGY,
                max_load=config.CH_MAX_LOAD,
                objective_weights=config.TDC_MOPSO_OBJECTIVE_WEIGHTS,
            )
            return selected, 0, {}

        if config.USE_BACKOFF_ELECTION:
            return self._elect_adaptive_backoff(drones, neighbor_map, scores)

        candidate_heads = sorted(drones, key=lambda d: (scores[d.identifier], d.residual_energy, -d.identifier), reverse=True)
        return candidate_heads[:max(1, len(drones) // 4)], 0, {}

    def _elect_adaptive_backoff(self, drones, neighbor_map, scores):
        backoff_entries = []
        score_max = max(max(scores.values()), 1e-9)
        backoff_map = {}
        for drone in drones:
            jitter = self.rng.uniform(0, config.CLUSTER_BACKOFF_MAX * 0.02)
            normalized = clamp01(scores[drone.identifier] / score_max)
            backoff = config.CLUSTER_BACKOFF_MAX * (1.0 - normalized) + jitter
            drone.cluster_backoff_time = backoff
            backoff_map[drone.identifier] = backoff
            self.metrics.record_backoff_time(backoff)
            backoff_entries.append((backoff, -scores[drone.identifier], drone.identifier, drone))

        selected = []
        covered = set()
        suppressed = 0
        for _, _, _, drone in sorted(backoff_entries):
            if drone.identifier in covered:
                suppressed += 1
                continue
            selected.append(drone)
            covered.add(drone.identifier)
            for neighbor in neighbor_map.get(drone.identifier, []):
                covered.add(neighbor.identifier)
        return selected, suppressed, backoff_map

    def _elect_lowest_id(self, drones, neighbor_map):
        selected = []
        covered = set()
        for drone in sorted(drones, key=lambda d: d.identifier):
            neighborhood = [drone] + neighbor_map.get(drone.identifier, [])
            if any(member.identifier in covered for member in neighborhood):
                continue
            selected.append(drone)
            for member in neighborhood:
                covered.add(member.identifier)
        if not selected and drones:
            selected.append(min(drones, key=lambda d: d.identifier))
        return selected

    def _elect_ranked_baseline(self, drones, neighbor_map, score_func):
        selected = []
        covered = set()
        ranked = sorted(drones, key=lambda d: (score_func(d, neighbor_map), -d.identifier), reverse=True)
        for drone in ranked:
            if drone.identifier in covered:
                continue
            selected.append(drone)
            covered.add(drone.identifier)
            for neighbor in neighbor_map.get(drone.identifier, []):
                covered.add(neighbor.identifier)
        return selected

    def _elect_leach(self, drones):
        head_count = max(1, int(round(len(drones) * config.LEACH_CLUSTER_HEAD_RATIO)))
        return self.rng.sample(drones, min(head_count, len(drones)))

    def _elect_kmeans(self, drones):
        if not drones:
            return []
        k = max(1, int(round(len(drones) / max(1, config.KMEANS_CLUSTER_DIVISOR))))
        coords = np.asarray([drone.coords for drone in drones], dtype=np.float32)
        initial_indices = self.rng.sample(range(len(drones)), min(k, len(drones)))
        centroids = coords[initial_indices]

        for _ in range(6):
            distances = np.linalg.norm(coords[:, None, :] - centroids[None, :, :], axis=2)
            labels = np.argmin(distances, axis=1)
            new_centroids = []
            for cluster_id in range(len(centroids)):
                members = coords[labels == cluster_id]
                if len(members) == 0:
                    new_centroids.append(centroids[cluster_id])
                else:
                    new_centroids.append(members.mean(axis=0))
            centroids = np.asarray(new_centroids, dtype=np.float32)

        selected = {}
        distances = np.linalg.norm(coords[:, None, :] - centroids[None, :, :], axis=2)
        labels = np.argmin(distances, axis=1)
        for cluster_id in range(len(centroids)):
            member_indices = [idx for idx, label in enumerate(labels) if label == cluster_id]
            if not member_indices:
                continue
            best_idx = min(member_indices, key=lambda idx: float(np.linalg.norm(coords[idx] - centroids[cluster_id])))
            selected[drones[best_idx].identifier] = drones[best_idx]
        return list(selected.values())

    def _wca_score(self, drone, neighbor_map):
        degree = len(neighbor_map.get(drone.identifier, []))
        degree_fit = 1.0 - abs(degree - config.CH_MAX_LOAD) / max(1, config.CH_MAX_LOAD)
        distance_sum = sum(euclidean_distance_3d(drone.coords, n.coords) for n in neighbor_map.get(drone.identifier, []))
        distance_score = 1.0 - clamp01(distance_sum / max(1.0, degree * config.COMMUNICATION_RANGE))
        mobility = 1.0 - clamp01(sum(v ** 2 for v in drone.velocity) ** 0.5 / max(1.0, config.DEFAULT_UAV_SPEED * 2))
        energy = clamp01(drone.residual_energy / float(config.INITIAL_ENERGY))
        return clamp01(0.35 * degree_fit + 0.25 * distance_score + 0.20 * mobility + 0.20 * energy)

    def _mobic_score(self, drone, neighbor_map):
        neighbors = neighbor_map.get(drone.identifier, [])
        if not neighbors:
            return 0.0
        relative = []
        for neighbor in neighbors:
            rv = sum((drone.velocity[idx] - neighbor.velocity[idx]) ** 2 for idx in range(3)) ** 0.5
            relative.append(rv)
        avg_relative = sum(relative) / len(relative)
        return 1.0 - clamp01(avg_relative / max(1.0, config.DEFAULT_UAV_SPEED * 2))

    def _mlsc_score(self, drone, neighbors, link_quality, density):
        energy = clamp01(drone.residual_energy / float(config.INITIAL_ENERGY))
        if not neighbors:
            return clamp01(0.5 * energy + 0.5 * link_quality)
        avg_distance = sum(euclidean_distance_3d(drone.coords, neighbor.coords) for neighbor in neighbors) / len(neighbors)
        location_stability = 1.0 - clamp01(avg_distance / float(config.COMMUNICATION_RANGE))
        relative_mobility = []
        for neighbor in neighbors:
            relative_velocity = sum((drone.velocity[idx] - neighbor.velocity[idx]) ** 2 for idx in range(3)) ** 0.5
            relative_mobility.append(relative_velocity)
        mobility_stability = 1.0 - clamp01((sum(relative_mobility) / len(relative_mobility)) / max(1.0, config.DEFAULT_UAV_SPEED * 2))
        return clamp01(0.30 * energy + 0.25 * link_quality + 0.20 * density + 0.15 * location_stability + 0.10 * mobility_stability)

    def get_cluster_head(self, drone_id):
        if drone_id < 0 or drone_id >= len(self.simulator.drones):
            return None
        drone = self.simulator.drones[drone_id]
        return drone.cluster_head

    def _apply_rotation(self, candidate_heads, drones, neighbor_map, scores, previous_head_ids):
        if not candidate_heads:
            return candidate_heads

        candidate_map = {drone.identifier: drone for drone in candidate_heads}
        retained = list(candidate_map.values())
        for head_id in previous_head_ids:
            if head_id < 0 or head_id >= len(self.simulator.drones):
                continue
            previous_head = self.simulator.drones[head_id]
            local_candidates = [previous_head] + neighbor_map.get(previous_head.identifier, [])
            best_candidate = max(local_candidates, key=lambda drone: scores.get(drone.identifier, 0.0))
            if best_candidate.identifier == previous_head.identifier:
                retained.append(previous_head)
                continue
            persistence_key = (previous_head.identifier, best_candidate.identifier)
            persistence = self.better_candidate_persistence.get(persistence_key, 0) + 1
            self.better_candidate_persistence[persistence_key] = persistence
            use_candidate = self.rotation_manager.should_rotate(previous_head, best_candidate, persistence)
            retained.append(best_candidate if use_candidate else previous_head)

        deduped = {}
        for head in retained:
            deduped[head.identifier] = head

        selected = []
        covered_ids = set()
        for candidate in sorted(deduped.values(), key=lambda drone: (scores[drone.identifier], drone.residual_energy, -drone.identifier), reverse=True):
            if candidate.identifier in covered_ids:
                continue
            selected.append(candidate)
            covered_ids.add(candidate.identifier)
            for neighbor in neighbor_map.get(candidate.identifier, []):
                covered_ids.add(neighbor.identifier)
        return selected
