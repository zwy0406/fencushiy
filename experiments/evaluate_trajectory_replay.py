import argparse
import json
import math
import os
import random
import sys
from types import SimpleNamespace

import numpy as np
import simpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mobility.gauss_markov_3d import GaussMarkov3D
from models.infer_models import OnlineTrajectoryModel
from utils import config


class _ZeroEnergyModel:
    @staticmethod
    def power_consumption(_speed):
        return 0.0


def _production_track(seed, track_id, speed, duration_s):
    env = simpy.Environment()
    rng = random.Random(seed + track_id)
    direction = rng.uniform(0, 2 * math.pi)
    pitch = rng.uniform(-0.05, 0.05)
    drone = SimpleNamespace(
        identifier=track_id,
        simulator=SimpleNamespace(seed=seed, env=env),
        coords=[
            rng.uniform(1, config.MAP_LENGTH - 1),
            rng.uniform(1, config.MAP_WIDTH - 1),
            rng.uniform(1, config.MAP_HEIGHT - 1),
        ],
        direction=direction,
        pitch=pitch,
        speed=speed,
        velocity=[
            speed * math.cos(direction) * math.cos(pitch),
            speed * math.sin(direction) * math.cos(pitch),
            speed * math.sin(pitch),
        ],
        velocity_mean=speed,
        direction_mean=direction,
        pitch_mean=pitch,
        energy_model=_ZeroEnergyModel(),
        consume_energy=lambda _value: None,
    )
    GaussMarkov3D(drone)
    states = []

    def record():
        while True:
            states.append(np.asarray([*drone.coords, *drone.velocity], dtype=np.float32))
            yield env.timeout(1e6)

    env.process(record())
    env.run(until=(duration_s + 0.01) * 1e6)
    return np.asarray(states)


def _clip(values):
    bounds = np.asarray([config.MAP_LENGTH, config.MAP_WIDTH, config.MAP_HEIGHT])
    return np.clip(values, 0, bounds)


def _summarize(distances, final_distances):
    values = np.concatenate(distances)
    finals = np.asarray(final_distances)
    return {
        'rmse_m': float(np.sqrt(np.mean(values ** 2))),
        'ade_m': float(np.mean(values)),
        'fde_m': float(np.mean(finals)),
        'forecast_count': int(len(finals)),
    }


def evaluate(model_path, config_path, seeds, speeds, tracks_per_setting=4,
             duration_s=100, history=20, horizon=5, stride=5):
    model = OnlineTrajectoryModel(model_path, config_path)
    if not model.available:
        raise RuntimeError(f'Unable to load candidate model: {model.status}')
    grouped = {}
    track_id = 0
    for seed in seeds:
        for speed in speeds:
            bucket = grouped.setdefault(str(speed), {'lstm': ([], []), 'kinematic': ([], [])})
            for _ in range(tracks_per_setting):
                states = _production_track(seed, track_id, speed, duration_s)
                for end in range(history, len(states) - horizon + 1, stride):
                    sequence = states[end - history:end]
                    actual = states[end:end + horizon, :3]
                    lstm = _clip(np.asarray(model.predict(sequence)))
                    steps = np.arange(1, horizon + 1).reshape(-1, 1)
                    kinematic = _clip(sequence[-1, :3] + sequence[-1, 3:6] * steps)
                    for name, predicted in (('lstm', lstm), ('kinematic', kinematic)):
                        distances = np.linalg.norm(predicted - actual, axis=-1)
                        bucket[name][0].append(distances)
                        bucket[name][1].append(distances[-1])
                track_id += 1

    result = {'model_status': model.status, 'by_speed': {}}
    all_values = {'lstm': ([], []), 'kinematic': ([], [])}
    for speed, bucket in grouped.items():
        result['by_speed'][speed] = {}
        for name in ('lstm', 'kinematic'):
            result['by_speed'][speed][name] = _summarize(*bucket[name])
            all_values[name][0].extend(bucket[name][0])
            all_values[name][1].extend(bucket[name][1])
    result['overall'] = {name: _summarize(*all_values[name]) for name in all_values}
    base = result['overall']['kinematic']['rmse_m']
    candidate = result['overall']['lstm']['rmse_m']
    result['rmse_improvement_vs_kinematic_pct'] = 100.0 * (base - candidate) / base
    return result


def main():
    parser = argparse.ArgumentParser(description='Replay a candidate model against production mobility code')
    parser.add_argument('--model-path', default=os.path.join('models', 'lstm', 'candidate_residual.pt'))
    parser.add_argument('--config-path', default=os.path.join('models', 'config', 'lstm_candidate_residual.json'))
    parser.add_argument('--seeds', default='3031,3032,3033')
    parser.add_argument('--speeds', default='12,20,28')
    parser.add_argument('--tracks-per-setting', type=int, default=4)
    parser.add_argument('--duration', type=int, default=100)
    parser.add_argument('--horizon', type=int, default=5)
    parser.add_argument('--stride', type=int, default=5)
    parser.add_argument('--output', default=os.path.join('results', 'trajectory_replay.json'))
    args = parser.parse_args()
    result = evaluate(
        args.model_path,
        args.config_path,
        [int(value) for value in args.seeds.split(',')],
        [float(value) for value in args.speeds.split(',')],
        args.tracks_per_setting,
        args.duration,
        horizon=args.horizon,
        stride=args.stride,
    )
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
