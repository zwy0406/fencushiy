import math

import numpy as np

from utils.util_function import euclidean_distance_3d


def _clamp01(value):
    return max(0.0, min(1.0, float(value)))


def mdcs_candidate_score(drone, neighbors, communication_range, reference_speed):
    """Score a real UAV as a compact, low-relative-velocity MDCS medoid."""
    if not neighbors:
        return 0.0

    distances = [euclidean_distance_3d(drone.coords, item.coords) for item in neighbors]
    relative_speeds = [
        math.sqrt(sum((drone.velocity[idx] - item.velocity[idx]) ** 2 for idx in range(3)))
        for item in neighbors
    ]
    compactness = 1.0 - _clamp01(sum(distances) / (len(distances) * communication_range))
    velocity_stability = 1.0 - _clamp01(
        sum(relative_speeds) / (len(relative_speeds) * max(1.0, 2.0 * reference_speed))
    )
    return _clamp01(0.75 * compactness + 0.25 * velocity_stability)


def select_mdcs_heads(drones, neighbor_map, communication_range, reference_speed,
                      backoff_max, rng):
    """Communication-simulator adaptation of the 2025 MDCS build-up process."""
    scores = {
        drone.identifier: mdcs_candidate_score(
            drone,
            neighbor_map.get(drone.identifier, []),
            communication_range,
            reference_speed,
        )
        for drone in drones
    }
    backoff_map = {
        drone.identifier: backoff_max * (1.0 - scores[drone.identifier])
        + rng.uniform(0.0, backoff_max * 0.02)
        for drone in drones
    }

    selected = []
    covered = set()
    suppressed = 0
    for drone in sorted(drones, key=lambda item: (backoff_map[item.identifier], item.identifier)):
        if drone.identifier in covered:
            suppressed += 1
            continue

        local = [drone] + [
            item for item in neighbor_map.get(drone.identifier, [])
            if item.identifier not in covered
        ]
        head = max(local, key=lambda item: (scores[item.identifier], -item.identifier))
        if any(item.identifier == head.identifier for item in selected):
            suppressed += 1
            covered.add(drone.identifier)
            continue
        selected.append(head)
        covered.add(head.identifier)
        for item in neighbor_map.get(head.identifier, []):
            covered.add(item.identifier)

    return selected, suppressed, backoff_map


def tdc_candidate_score(drone, neighbors, initial_energy, communication_range,
                        reference_speed):
    """Transparent CH utility used to repair and break ties in TDC-MOPSO."""
    energy = _clamp01(drone.residual_energy / float(initial_energy))
    if not neighbors:
        return 0.35 * energy
    distances = [euclidean_distance_3d(drone.coords, item.coords) for item in neighbors]
    relative_speeds = [
        math.sqrt(sum((drone.velocity[idx] - item.velocity[idx]) ** 2 for idx in range(3)))
        for item in neighbors
    ]
    compactness = 1.0 - _clamp01(sum(distances) / (len(distances) * communication_range))
    stability = 1.0 - _clamp01(
        sum(relative_speeds) / (len(relative_speeds) * max(1.0, 2.0 * reference_speed))
    )
    return _clamp01(0.40 * energy + 0.35 * compactness + 0.25 * stability)


class TdcMopsoSelector:
    """Binary MOPSO adaptation for task-driven CH selection in this simulator.

    The source paper uses heterogeneous mission resources that UavNetSim does not
    model. Here, unused CH capacity is the resource-waste objective; energy,
    member distance, handover and control overhead remain separate objectives.
    """

    def __init__(self, rng, swarm_size=12, iterations=8, archive_size=24,
                 inertia=0.72, cognitive=1.45, social=1.45, mutation_rate=0.05):
        self.rng = rng
        self.swarm_size = max(4, int(swarm_size))
        self.iterations = max(1, int(iterations))
        self.archive_size = max(4, int(archive_size))
        self.inertia = float(inertia)
        self.cognitive = float(cognitive)
        self.social = float(social)
        self.mutation_rate = _clamp01(mutation_rate)

    def select(self, drones, neighbor_map, previous_head_ids, communication_range,
               reference_speed, initial_energy, max_load, objective_weights):
        if not drones:
            return []

        ordered = sorted(drones, key=lambda item: item.identifier)
        n_nodes = len(ordered)
        id_to_index = {drone.identifier: idx for idx, drone in enumerate(ordered)}
        adjacency = np.eye(n_nodes, dtype=bool)
        distance = np.full((n_nodes, n_nodes), np.inf, dtype=np.float64)
        np.fill_diagonal(distance, 0.0)
        for idx, drone in enumerate(ordered):
            for neighbor in neighbor_map.get(drone.identifier, []):
                other_idx = id_to_index[neighbor.identifier]
                adjacency[idx, other_idx] = True
                distance[idx, other_idx] = euclidean_distance_3d(drone.coords, neighbor.coords)

        utility = np.asarray([
            tdc_candidate_score(
                drone,
                neighbor_map.get(drone.identifier, []),
                initial_energy,
                communication_range,
                reference_speed,
            )
            for drone in ordered
        ])
        energy = np.asarray([
            _clamp01(drone.residual_energy / float(initial_energy)) for drone in ordered
        ])
        previous = {id_to_index[item] for item in previous_head_ids if item in id_to_index}
        weights = np.asarray(objective_weights, dtype=np.float64)
        weights = weights / max(float(weights.sum()), 1e-12)

        np_rng = np.random.default_rng(self.rng.randrange(0, 2 ** 32))
        positions = np_rng.uniform(-1.5, 1.5, size=(self.swarm_size, n_nodes))
        velocities = np_rng.uniform(-0.25, 0.25, size=(self.swarm_size, n_nodes))
        pbest_positions = positions.copy()
        pbest_objectives = None
        archive = []

        for _ in range(self.iterations):
            probabilities = 1.0 / (1.0 + np.exp(-np.clip(positions, -20.0, 20.0)))
            particles = probabilities > np_rng.random(probabilities.shape)
            if self.mutation_rate > 0.0:
                particles ^= np_rng.random(particles.shape) < self.mutation_rate

            repaired = [self._repair(bits, adjacency, utility) for bits in particles]
            objectives = np.asarray([
                self._objectives(
                    bits,
                    adjacency,
                    distance,
                    energy,
                    previous,
                    communication_range,
                    max_load,
                )
                for bits in repaired
            ])

            if pbest_objectives is None:
                pbest_objectives = objectives.copy()
                pbest_positions = positions.copy()
            else:
                for idx in range(self.swarm_size):
                    if self._dominates(objectives[idx], pbest_objectives[idx]) or (
                        not self._dominates(pbest_objectives[idx], objectives[idx])
                        and float(np.dot(objectives[idx], weights))
                        < float(np.dot(pbest_objectives[idx], weights))
                    ):
                        pbest_objectives[idx] = objectives[idx]
                        pbest_positions[idx] = positions[idx]

            archive = self._update_archive(archive, repaired, objectives, weights)
            leader_bits, _ = min(archive, key=lambda item: float(np.dot(item[1], weights)))
            leader_position = np.where(leader_bits, 2.0, -2.0)
            r1 = np_rng.random(positions.shape)
            r2 = np_rng.random(positions.shape)
            velocities = (
                self.inertia * velocities
                + self.cognitive * r1 * (pbest_positions - positions)
                + self.social * r2 * (leader_position - positions)
            )
            positions = np.clip(positions + velocities, -6.0, 6.0)

        best_bits, _ = min(archive, key=lambda item: float(np.dot(item[1], weights)))
        return [ordered[idx] for idx, selected in enumerate(best_bits) if selected]

    @staticmethod
    def _repair(bits, adjacency, utility):
        selected = np.asarray(bits, dtype=bool).copy()
        if not selected.any():
            selected[int(np.argmax(utility))] = True

        covered = adjacency[:, selected].any(axis=1)
        while not covered.all():
            uncovered = ~covered
            gains = adjacency[uncovered].sum(axis=0).astype(np.float64)
            gains += utility
            gains[selected] = -1.0
            selected[int(np.argmax(gains))] = True
            covered = adjacency[:, selected].any(axis=1)

        for idx in np.flatnonzero(selected)[::-1]:
            trial = selected.copy()
            trial[idx] = False
            if trial.any() and adjacency[:, trial].any(axis=1).all():
                selected = trial
        return selected

    @staticmethod
    def _objectives(bits, adjacency, distance, energy, previous, communication_range,
                    max_load):
        head_indices = np.flatnonzero(bits)
        member_distances = []
        loads = np.zeros(len(head_indices), dtype=np.float64)
        for node_idx in range(adjacency.shape[0]):
            reachable = [
                idx for idx, head_idx in enumerate(head_indices)
                if adjacency[node_idx, head_idx]
            ]
            best_local = min(reachable, key=lambda idx: distance[node_idx, head_indices[idx]])
            loads[best_local] += 1.0
            member_distances.append(distance[node_idx, head_indices[best_local]])

        capacity_waste = np.mean(np.abs(loads - max_load) / max(1.0, float(max_load)))
        energy_cost = 1.0 - float(np.mean(energy[head_indices]))
        distance_cost = float(np.mean(member_distances)) / max(1.0, communication_range)
        current = set(int(idx) for idx in head_indices)
        if previous:
            handover_cost = len(current.symmetric_difference(previous)) / max(1, len(current | previous))
        else:
            handover_cost = 0.0
        overhead_cost = len(head_indices) / float(adjacency.shape[0])
        return np.asarray([
            capacity_waste,
            energy_cost,
            distance_cost,
            handover_cost,
            overhead_cost,
        ])

    @staticmethod
    def _dominates(left, right):
        return bool(np.all(left <= right) and np.any(left < right))

    def _update_archive(self, archive, particles, objectives, weights):
        candidates = list(archive)
        for bits, objective in zip(particles, objectives):
            key = tuple(bool(value) for value in bits)
            if any(tuple(bool(value) for value in item[0]) == key for item in candidates):
                continue
            candidates.append((bits.copy(), objective.copy()))

        nondominated = []
        for idx, candidate in enumerate(candidates):
            if any(
                other_idx != idx and self._dominates(other[1], candidate[1])
                for other_idx, other in enumerate(candidates)
            ):
                continue
            nondominated.append(candidate)
        nondominated.sort(key=lambda item: float(np.dot(item[1], weights)))
        return nondominated[:self.archive_size]
