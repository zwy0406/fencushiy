import argparse
import json
import os

import numpy as np
import simpy

from experiments.run_experiment import reset_packet_ids
from simulator.simulator import Simulator
from utils import config
from utils.util_function import euclidean_distance_3d


def _snapshot_by_time(drone):
    return {entry['time']: entry for entry in getattr(drone, 'trajectory_trace', [])}


def _build_feature_row(state, neighbors):
    energy_ratio = float(state.get('residual_energy', config.INITIAL_ENERGY)) / float(config.INITIAL_ENERGY)
    speed = float(state.get('speed', 0.0))
    speed_ratio = min(1.0, speed / max(1.0, config.DEFAULT_UAV_SPEED * 2))
    degree_ratio = min(1.0, len(neighbors) / max(1, config.NUMBER_OF_DRONES - 1))
    if neighbors:
        link_quality = sum(
            max(0.0, 1.0 - euclidean_distance_3d(state['coords'], other['coords']) / float(config.COMMUNICATION_RANGE))
            for other in neighbors
        ) / len(neighbors)
    else:
        link_quality = 0.0
    return [energy_ratio, link_quality, degree_ratio, speed_ratio]


def _neighbor_indices(states, index):
    origin = states[index]
    neighbors = []
    for candidate_index, candidate in enumerate(states):
        if candidate_index == index:
            continue
        if euclidean_distance_3d(origin['coords'], candidate['coords']) <= config.COMMUNICATION_RANGE:
            neighbors.append(candidate_index)
    return neighbors


def _build_graph_sample(states_now, states_future):
    node_count = len(states_now)
    adjacency = np.eye(node_count, dtype=np.float32)
    features = []
    labels = []

    current_neighbors = {idx: _neighbor_indices(states_now, idx) for idx in range(node_count)}
    future_neighbors = [{idx: _neighbor_indices(step_states, idx) for idx in range(node_count)} for step_states in states_future]

    for idx, state in enumerate(states_now):
        neighbors = [states_now[n_idx] for n_idx in current_neighbors[idx]]
        features.append(_build_feature_row(state, neighbors))
        for n_idx in current_neighbors[idx]:
            adjacency[idx, n_idx] = 1.0

        current_set = set(current_neighbors[idx])
        stability_scores = []
        for future_map in future_neighbors:
            future_set = set(future_map[idx])
            union = current_set | future_set
            if not union:
                stability_scores.append(1.0)
            else:
                stability_scores.append(len(current_set & future_set) / len(union))
        degree_ratio = min(1.0, len(current_set) / max(1, node_count - 1))
        labels.append(0.5 * degree_ratio + 0.5 * (sum(stability_scores) / len(stability_scores) if stability_scores else 0.0))

    return np.asarray(features, dtype=np.float32), adjacency, np.asarray(labels, dtype=np.float32)


def _collect_joint_timesteps(drones):
    time_sets = [set(entry['time'] for entry in getattr(drone, 'trajectory_trace', [])) for drone in drones]
    if not time_sets:
        return []
    return sorted(set.intersection(*time_sets))


def export_dataset(output_dir, seed, n_drones, speed, enable_poi):
    config.ROUTING_PROTOCOL = 'DSDV'
    config.NUMBER_OF_DRONES = n_drones
    config.MAX_TTL = n_drones + 1
    config.DEFAULT_UAV_SPEED = speed
    config.ENABLE_VISUALIZATION = False
    config.ENABLE_PLOTS = False
    config.ENABLE_POI = enable_poi
    config.EXPORT_DATASET = True
    config.EXPORT_GRAPH_DATASET = True
    config.EXPORT_TRAJECTORY_DATASET = True
    config.DATASET_SCENARIO_TAG = f'n{n_drones}_v{speed}_seed{seed}'
    config.RESULTS_DIR = output_dir
    reset_packet_ids()

    env = simpy.Environment()
    channel_states = {i: simpy.Resource(env, capacity=1) for i in range(n_drones)}
    simulator = Simulator(seed=seed, env=env, channel_states=channel_states, n_drones=n_drones)
    env.run(until=config.SIM_TIME)

    os.makedirs(output_dir, exist_ok=True)
    trajectory_path = os.path.join(output_dir, 'trajectory_dataset.npz')
    graph_path = os.path.join(output_dir, 'graph_dataset.npz')
    meta_path = os.path.join(output_dir, 'dataset_meta.json')

    trajectory_inputs = []
    trajectory_targets = []
    for drone in simulator.drones:
        trace = getattr(drone, 'trajectory_trace', [])
        if len(trace) <= config.TRAJECTORY_HISTORY_SIZE + config.PREDICTION_HORIZON:
            continue
        for anchor in range(config.TRAJECTORY_HISTORY_SIZE, len(trace) - config.PREDICTION_HORIZON):
            history = trace[anchor - config.TRAJECTORY_HISTORY_SIZE:anchor]
            future = trace[anchor:anchor + config.PREDICTION_HORIZON]
            trajectory_inputs.append([
                [
                    step['coords'][0], step['coords'][1], step['coords'][2],
                    step['velocity'][0], step['velocity'][1], step['velocity'][2],
                ]
                for step in history
            ])
            trajectory_targets.append([list(step['coords']) for step in future])

    joint_times = _collect_joint_timesteps(simulator.drones)
    drone_snapshots = [_snapshot_by_time(drone) for drone in simulator.drones]
    graph_features = []
    graph_adjacency = []
    graph_labels = []
    graph_times = []

    future_step = int(1 * 1e6)
    for current_time in joint_times:
        future_times = [current_time + offset * future_step for offset in range(1, config.PREDICTION_HORIZON + 1)]
        if any(f_time not in drone_snapshots[0] for f_time in future_times):
            continue
        try:
            states_now = [snapshot[current_time] for snapshot in drone_snapshots]
            states_future = [[snapshot[f_time] for snapshot in drone_snapshots] for f_time in future_times]
        except KeyError:
            continue
        features, adjacency, labels = _build_graph_sample(states_now, states_future)
        graph_features.append(features)
        graph_adjacency.append(adjacency)
        graph_labels.append(labels)
        graph_times.append(current_time)

    np.savez_compressed(
        trajectory_path,
        inputs=np.asarray(trajectory_inputs, dtype=np.float32),
        targets=np.asarray(trajectory_targets, dtype=np.float32),
    )
    np.savez_compressed(
        graph_path,
        features=np.asarray(graph_features, dtype=np.float32),
        adjacency=np.asarray(graph_adjacency, dtype=np.float32),
        labels=np.asarray(graph_labels, dtype=np.float32),
        times=np.asarray(graph_times, dtype=np.int64),
    )

    metadata = {
        'seed': seed,
        'number_of_drones': n_drones,
        'speed_mps': speed,
        'enable_poi': enable_poi,
        'trajectory_samples': int(len(trajectory_inputs)),
        'graph_samples': int(len(graph_features)),
        'history_size': config.TRAJECTORY_HISTORY_SIZE,
        'prediction_horizon': config.PREDICTION_HORIZON,
        'mobility_model': config.MOBILITY_MODEL,
    }
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

    return {
        'trajectory_dataset': trajectory_path,
        'graph_dataset': graph_path,
        'meta': meta_path,
        'trajectory_samples': len(trajectory_inputs),
        'graph_samples': len(graph_features),
    }


def main():
    parser = argparse.ArgumentParser(description='Export trajectory and graph datasets for GA-MP-DCA')
    parser.add_argument('--output-dir', default=os.path.join(config.DATA_DIR, 'ga_mp_dca'))
    parser.add_argument('--seed', type=int, default=2025)
    parser.add_argument('--n-drones', type=int, default=60)
    parser.add_argument('--speed', type=int, default=20)
    parser.add_argument('--enable-poi', action='store_true')
    args = parser.parse_args()

    result = export_dataset(
        output_dir=args.output_dir,
        seed=args.seed,
        n_drones=args.n_drones,
        speed=args.speed,
        enable_poi=args.enable_poi,
    )
    print(result)


if __name__ == '__main__':
    main()
