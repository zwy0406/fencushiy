import unittest
from types import SimpleNamespace

from topology.mwmp_dca.predictor import KinematicTrajectoryPredictor, LstmTrajectoryPredictor
from topology.mwmp_dca.recent_baselines import TdcMopsoSelector, select_mdcs_heads
from topology.mwmp_dca.cluster_metrics import ClusterMetrics
from topology.mwmp_dca.cluster_manager import ClusterManager
from topology.mwmp_dca.cluster_rotation import ClusterRotationManager
from topology.mwmp_dca.trajectory_let_calculator import trajectory_based_let
from topology.mwmp_dca.weight_calculator import WeightCalculator
from routing.mwmp_dca.mwmp_dca_routing import MwmpDcaRouting
from utils import config


class MwmpDcaUnitTests(unittest.TestCase):
    def test_trajectory_let_stops_when_link_breaks(self):
        traj_a = [(0, 0, 0), (10, 0, 0), (20, 0, 0)]
        traj_b = [(0, 0, 0), (15, 0, 0), (300, 0, 0)]
        self.assertEqual(trajectory_based_let(traj_a, traj_b, communication_range=20), 2.0)

    def test_weight_prefers_stable_high_energy_node(self):
        calculator = WeightCalculator(profile_name='W2')
        high = calculator.score(1.0, 0.9, 0.7, 1.0, 0.1, poi_ratio=0.5)
        low = calculator.score(0.2, 0.2, 0.2, 0.1, 0.9, poi_ratio=0.0)
        self.assertGreater(high, low)

    def test_backoff_is_shorter_for_higher_weight(self):
        high_weight = 0.9
        low_weight = 0.2
        high_backoff = config.CLUSTER_BACKOFF_MAX * (1.0 - high_weight)
        low_backoff = config.CLUSTER_BACKOFF_MAX * (1.0 - low_weight)
        self.assertLess(high_backoff, low_backoff)

    def test_predictors_return_prediction_horizon(self):
        drone = SimpleNamespace(
            coords=(10, 10, 10),
            velocity=(1, 2, 0),
            trajectory_history=[
                {'coords': (10, 10, 10), 'velocity': (1, 2, 0)},
                {'coords': (11, 12, 10), 'velocity': (1, 2, 0)},
                {'coords': (12, 14, 10), 'velocity': (1, 2, 0)},
            ],
        )
        self.assertEqual(len(KinematicTrajectoryPredictor().predict(drone, 5)), 5)
        self.assertEqual(len(LstmTrajectoryPredictor().predict(drone, 5)), 5)

    def test_mdcs_covers_all_nodes(self):
        import random

        drones = [
            SimpleNamespace(identifier=0, coords=(0, 0, 0), velocity=(1, 0, 0)),
            SimpleNamespace(identifier=1, coords=(10, 0, 0), velocity=(1, 0, 0)),
            SimpleNamespace(identifier=2, coords=(300, 0, 0), velocity=(1, 0, 0)),
        ]
        neighbor_map = {0: [drones[1]], 1: [drones[0]], 2: []}
        heads, _, _ = select_mdcs_heads(drones, neighbor_map, 50, 10, 1000, random.Random(7))
        covered = {head.identifier for head in heads}
        for head in heads:
            covered.update(item.identifier for item in neighbor_map[head.identifier])
        self.assertEqual(covered, {0, 1, 2})

    def test_tdc_mopso_returns_a_dominating_head_set(self):
        import random

        drones = [
            SimpleNamespace(
                identifier=idx,
                coords=(idx * 20, 0, 0),
                velocity=(1, 0, 0),
                residual_energy=20000,
            )
            for idx in range(4)
        ]
        neighbor_map = {
            drone.identifier: [
                other for other in drones
                if other.identifier != drone.identifier
                and abs(other.coords[0] - drone.coords[0]) <= 25
            ]
            for drone in drones
        }
        selector = TdcMopsoSelector(random.Random(11), swarm_size=6, iterations=3)
        heads = selector.select(
            drones,
            neighbor_map,
            previous_head_ids=set(),
            communication_range=25,
            reference_speed=10,
            initial_energy=20000,
            max_load=2,
            objective_weights=[0.25, 0.25, 0.20, 0.20, 0.10],
        )
        covered = {head.identifier for head in heads}
        for head in heads:
            covered.update(item.identifier for item in neighbor_map[head.identifier])
        self.assertEqual(covered, {0, 1, 2, 3})

    def test_cluster_metrics_report_normalized_churn_and_active_tenure(self):
        metrics = ClusterMetrics()
        metrics.record_cluster_snapshot([(1, [1, 2]), (3, [3, 4])], round_counter=1)
        metrics.record_cluster_snapshot([(1, [1, 2, 3]), (4, [4])], round_counter=2)
        metrics.record_backbone_connectivity(0.75, 0.50, 0.80, 0.90)
        summary = metrics.summary()
        self.assertAlmostEqual(summary['cluster_head_churn_ratio'], 2 / 3)
        self.assertGreater(summary['mean_ch_tenure_rounds'], 0)
        self.assertGreater(summary['mean_cluster_tenure_rounds'], 0)
        self.assertEqual(summary['mean_backbone_connectivity_ratio'], 0.75)
        self.assertEqual(summary['mean_bs_reachability_ratio'], 0.50)
        self.assertEqual(summary['mean_backbone_path_preservation_ratio'], 0.80)
        self.assertEqual(summary['mean_bs_reachability_efficiency'], 0.90)
        self.assertEqual(summary['backbone_partition_ratio'], 1.0)

    def test_adaptive_rotation_keeps_stable_head_for_small_score_gain(self):
        manager = ClusterRotationManager()
        current = SimpleNamespace(
            residual_energy=config.INITIAL_ENERGY,
            cluster_age=5,
            avg_let=config.PREDICTION_HORIZON,
            mobility_factor=0.1,
            cluster_members=[1, 2],
            cluster_weight=0.60,
        )
        candidate = SimpleNamespace(
            avg_let=config.PREDICTION_HORIZON,
            mobility_factor=0.1,
            cluster_weight=0.70,
        )
        original = config.ADAPTIVE_CH_ROTATION
        original_bonus = config.CH_ROTATION_STABILITY_MARGIN_BONUS
        try:
            config.ADAPTIVE_CH_ROTATION = True
            config.CH_ROTATION_STABILITY_MARGIN_BONUS = 0.05
            self.assertFalse(manager.should_rotate(current, candidate, stable_rounds=3))
        finally:
            config.ADAPTIVE_CH_ROTATION = original
            config.CH_ROTATION_STABILITY_MARGIN_BONUS = original_bonus

    def test_adaptive_rotation_replaces_low_tlet_head_with_better_link(self):
        manager = ClusterRotationManager()
        current = SimpleNamespace(
            residual_energy=config.INITIAL_ENERGY,
            cluster_age=5,
            avg_let=1.0,
            mobility_factor=0.1,
            cluster_members=[1, 2],
            cluster_weight=0.60,
        )
        candidate = SimpleNamespace(
            avg_let=config.PREDICTION_HORIZON,
            mobility_factor=0.1,
            cluster_weight=0.59,
        )
        original = config.ADAPTIVE_CH_ROTATION
        try:
            config.ADAPTIVE_CH_ROTATION = True
            self.assertTrue(manager.should_rotate(current, candidate, stable_rounds=1))
        finally:
            config.ADAPTIVE_CH_ROTATION = original

    def test_backbone_connector_selects_intermediate_node(self):
        base = SimpleNamespace(identifier=0, coords=(0, 0, 0), is_base_station=True)
        relay = SimpleNamespace(identifier=1, coords=(90, 0, 0), is_base_station=False)
        head = SimpleNamespace(identifier=2, coords=(180, 0, 0), is_base_station=False)
        manager = SimpleNamespace(
            simulator=SimpleNamespace(drones=[base, relay, head]),
        )
        manager._shortest_backbone_path = (
            lambda start, targets, adjacency, scores, previous: ClusterManager._shortest_backbone_path(
                manager, start, targets, adjacency, scores, previous
            )
        )
        original = config.USE_BACKBONE_CONNECTORS
        original_range = config.COMMUNICATION_RANGE
        try:
            config.USE_BACKBONE_CONNECTORS = True
            config.COMMUNICATION_RANGE = 100
            connected = ClusterManager._connect_backbone(
                manager,
                [head],
                [relay, head],
                {1: 0.7, 2: 0.9},
                set(),
            )
            self.assertEqual({drone.identifier for drone in connected}, {1, 2})
        finally:
            config.USE_BACKBONE_CONNECTORS = original
            config.COMMUNICATION_RANGE = original_range

    def test_backbone_relay_is_independent_from_cluster_head_role(self):
        relay = SimpleNamespace(cluster_role='CM', is_backbone_connector=True)
        member = SimpleNamespace(cluster_role='CM', is_backbone_connector=False)
        head = SimpleNamespace(cluster_role='CH', is_backbone_connector=False)
        self.assertTrue(MwmpDcaRouting._is_backbone_node(relay))
        self.assertTrue(MwmpDcaRouting._is_backbone_node(head))
        self.assertFalse(MwmpDcaRouting._is_backbone_node(member))

if __name__ == '__main__':
    unittest.main()
