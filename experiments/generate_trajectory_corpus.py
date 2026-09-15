import argparse
import json
import math
import os
import random
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from utils import config


def _parse_values(value, caster):
    return [caster(item.strip()) for item in value.split(',') if item.strip()]


def _simulate_track(seed, track_id, mean_speed, duration_s):
    """Reproduce GaussMarkov3D at 0.1 s resolution and sample each second."""
    rng = random.Random(seed + track_id + 1)
    bounds = np.asarray([config.MAP_LENGTH, config.MAP_WIDTH, config.MAP_HEIGHT], dtype=np.float64)
    position = np.asarray([rng.uniform(1.0, value - 1.0) for value in bounds])
    direction = rng.uniform(0.0, 2.0 * math.pi)
    pitch = rng.uniform(-0.05, 0.05)
    direction_mean, pitch_mean = direction, pitch
    velocity = np.asarray([
        mean_speed * math.cos(direction) * math.cos(pitch),
        mean_speed * math.sin(direction) * math.cos(pitch),
        mean_speed * math.sin(pitch),
    ])
    alpha = 0.85
    random_scale = math.sqrt(1.0 - alpha * alpha)
    states = [np.concatenate([position.copy(), velocity.copy()])]

    for step in range(int(duration_s / 0.1)):
        position += velocity * 0.1
        if step % 5 == 0:
            speed = alpha * np.linalg.norm(velocity) + (1.0 - alpha) * mean_speed
            speed += random_scale * rng.normalvariate(0, 1)
            direction = alpha * direction + (1.0 - alpha) * direction_mean
            direction += random_scale * rng.normalvariate(0, 1)
            pitch = alpha * pitch + (1.0 - alpha) * pitch_mean
            pitch += random_scale * rng.normalvariate(0, 1)
            velocity = np.asarray([
                speed * math.cos(direction) * math.cos(pitch),
                speed * math.sin(direction) * math.cos(pitch),
                speed * math.sin(pitch),
            ])

        for axis in range(3):
            if position[axis] < 1.0 or position[axis] > bounds[axis] - 1.0:
                velocity[axis] = -velocity[axis]
                if axis == 0:
                    direction_mean = math.pi - direction_mean
                elif axis == 1:
                    direction_mean = -direction_mean
                else:
                    pitch_mean = -pitch_mean
            position[axis] = max(1.0, min(float(position[axis]), bounds[axis] - 1.0))
        # GaussMarkov3D.boundary_test returns the (possibly reflected) means as
        # the next direction and pitch state.
        direction, pitch = direction_mean, pitch_mean
        if (step + 1) % 10 == 0:
            states.append(np.concatenate([position.copy(), velocity.copy()]))
    return np.asarray(states, dtype=np.float32)


def generate(output_path, seeds, speeds, tracks_per_setting=12, duration_s=180,
             history=20, horizon=5, stride=2):
    inputs, targets, track_ids, sample_speeds, sample_seeds = [], [], [], [], []
    track_id = 0
    for seed in seeds:
        for speed in speeds:
            for _ in range(tracks_per_setting):
                states = _simulate_track(seed, track_id, speed, duration_s)
                for end in range(history, len(states) - horizon + 1, stride):
                    inputs.append(states[end - history:end])
                    targets.append(states[end:end + horizon, :3])
                    track_ids.append(track_id)
                    sample_speeds.append(speed)
                    sample_seeds.append(seed)
                track_id += 1

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    np.savez_compressed(
        output_path,
        inputs=np.asarray(inputs, dtype=np.float32),
        targets=np.asarray(targets, dtype=np.float32),
        track_ids=np.asarray(track_ids, dtype=np.int32),
        speeds=np.asarray(sample_speeds, dtype=np.float32),
        seeds=np.asarray(sample_seeds, dtype=np.int32),
    )
    metadata = {
        'generator': 'GaussMarkov3D-compatible mobility-only corpus',
        'seeds': seeds,
        'speeds_mps': speeds,
        'tracks_per_setting': tracks_per_setting,
        'track_count': track_id,
        'duration_s': duration_s,
        'history_s': history,
        'horizon_s': horizon,
        'stride_s': stride,
        'sample_count': len(inputs),
    }
    with open(os.path.splitext(output_path)[0] + '.json', 'w', encoding='utf-8') as stream:
        json.dump(metadata, stream, indent=2)
    return metadata


def main():
    parser = argparse.ArgumentParser(description='Generate grouped Gauss-Markov trajectory data')
    parser.add_argument('--output', default=os.path.join(config.DATA_DIR, 'trajectory_corpus', 'trajectory_dataset.npz'))
    parser.add_argument('--seeds', default='2025,2026,2027,2028,2029')
    parser.add_argument('--speeds', default='10,15,20,25,30')
    parser.add_argument('--tracks-per-setting', type=int, default=12)
    parser.add_argument('--duration', type=int, default=180)
    parser.add_argument('--history', type=int, default=20)
    parser.add_argument('--horizon', type=int, default=5)
    parser.add_argument('--stride', type=int, default=2)
    args = parser.parse_args()
    result = generate(
        args.output,
        _parse_values(args.seeds, int),
        _parse_values(args.speeds, float),
        args.tracks_per_setting,
        args.duration,
        args.history,
        args.horizon,
        args.stride,
    )
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
