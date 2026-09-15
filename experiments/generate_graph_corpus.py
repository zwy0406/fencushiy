import argparse
import json
import os
import random
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from experiments.export_dataset import _build_graph_sample
from experiments.generate_trajectory_corpus import _parse_values, _simulate_track
from utils import config


def _state(row, energy_ratio):
    return {
        'coords': tuple(float(value) for value in row[:3]),
        'velocity': tuple(float(value) for value in row[3:6]),
        'speed': float(np.linalg.norm(row[3:6])),
        'residual_energy': float(config.INITIAL_ENERGY * energy_ratio),
    }


def generate(output_path, seeds, speeds, scenarios_per_setting=6, n_drones=20,
             duration_s=80, horizon=5, stride=5, comm_range=200):
    original_count = config.NUMBER_OF_DRONES
    original_speed = config.DEFAULT_UAV_SPEED
    original_range = config.COMMUNICATION_RANGE
    features, adjacency, labels, scenario_ids = [], [], [], []
    sample_speeds, sample_seeds = [], []
    scenario_id = 0
    track_id = 0
    try:
        config.NUMBER_OF_DRONES = n_drones
        config.COMMUNICATION_RANGE = comm_range
        for seed in seeds:
            for speed in speeds:
                config.DEFAULT_UAV_SPEED = speed
                for _ in range(scenarios_per_setting):
                    tracks = []
                    energy_rng = random.Random(seed * 10000 + scenario_id)
                    energies = [energy_rng.uniform(0.65, 1.0) for _ in range(n_drones)]
                    for _node in range(n_drones):
                        tracks.append(_simulate_track(seed, track_id, speed, duration_s))
                        track_id += 1
                    for anchor in range(10, duration_s - horizon + 1, stride):
                        states_now = [_state(track[anchor], energies[idx]) for idx, track in enumerate(tracks)]
                        states_future = [
                            [_state(track[anchor + step], energies[idx]) for idx, track in enumerate(tracks)]
                            for step in range(1, horizon + 1)
                        ]
                        sample_features, sample_adjacency, sample_labels = _build_graph_sample(
                            states_now, states_future)
                        features.append(sample_features)
                        adjacency.append(sample_adjacency)
                        labels.append(sample_labels)
                        scenario_ids.append(scenario_id)
                        sample_speeds.append(speed)
                        sample_seeds.append(seed)
                    scenario_id += 1
    finally:
        config.NUMBER_OF_DRONES = original_count
        config.DEFAULT_UAV_SPEED = original_speed
        config.COMMUNICATION_RANGE = original_range

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    np.savez_compressed(
        output_path,
        features=np.asarray(features, dtype=np.float32),
        adjacency=np.asarray(adjacency, dtype=np.float32),
        labels=np.asarray(labels, dtype=np.float32),
        scenario_ids=np.asarray(scenario_ids, dtype=np.int32),
        speeds=np.asarray(sample_speeds, dtype=np.float32),
        seeds=np.asarray(sample_seeds, dtype=np.int32),
    )
    metadata = {
        'generator': 'GaussMarkov3D-compatible graph corpus',
        'seeds': seeds,
        'speeds_mps': speeds,
        'scenarios_per_setting': scenarios_per_setting,
        'scenario_count': scenario_id,
        'n_drones': n_drones,
        'duration_s': duration_s,
        'prediction_horizon_s': horizon,
        'snapshot_stride_s': stride,
        'comm_range_m': comm_range,
        'sample_count': len(features),
    }
    with open(os.path.splitext(output_path)[0] + '.json', 'w', encoding='utf-8') as stream:
        json.dump(metadata, stream, indent=2)
    return metadata


def main():
    parser = argparse.ArgumentParser(description='Generate grouped graph-stability training data')
    parser.add_argument('--output', default=os.path.join(config.DATA_DIR, 'graph_corpus', 'graph_dataset.npz'))
    parser.add_argument('--seeds', default='2025,2026,2027,2028,2029')
    parser.add_argument('--speeds', default='10,15,20,25,30')
    parser.add_argument('--scenarios-per-setting', type=int, default=6)
    parser.add_argument('--n-drones', type=int, default=20)
    parser.add_argument('--duration', type=int, default=80)
    parser.add_argument('--horizon', type=int, default=5)
    parser.add_argument('--stride', type=int, default=5)
    parser.add_argument('--comm-range', type=float, default=200)
    args = parser.parse_args()
    result = generate(
        args.output,
        _parse_values(args.seeds, int),
        _parse_values(args.speeds, float),
        args.scenarios_per_setting,
        args.n_drones,
        args.duration,
        args.horizon,
        args.stride,
        args.comm_range,
    )
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
