"""Profile frozen Proposed routing epochs without timing the full simulator."""

import argparse
import csv
import json
import logging
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path


SEEDS = range(2030, 2035)
SIZES = (60, 80, 100)
PROFILE_SECONDS = 30
WARMUP_EPOCHS = 5
TRACE_ROOTS = {
    60: Path('results/e1_n60_a3_seeds2030_2039_20261006'),
    80: Path('results/f0_formal_a3_seeds2030_2039_20261005'),
    100: Path('results/e1_n100_a3_seeds2030_2039_20261006'),
}


def trace_path(size, seed):
    return TRACE_ROOTS[size] / 'mobility_traces' / f'seed{seed}_n{size}_v15.json'


def cpu_model():
    path = Path('/proc/cpuinfo')
    if path.is_file():
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.startswith('model name'):
                return line.split(':', 1)[1].strip()
    return platform.processor()


def memory_bytes():
    path = Path('/proc/meminfo')
    if path.is_file():
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.startswith('MemTotal:'):
                return int(line.split()[1]) * 1024
    return None


def manifest():
    return {
        'experiment': 'E10',
        'scope': 'Proposed A3 algorithm-only epoch timing',
        'git_head': subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], text=True
        ).strip(),
        'sizes_including_bs': list(SIZES),
        'seeds': list(SEEDS),
        'speed_mps': 15,
        'traffic_rate_pps_per_uav': 2,
        'comm_range_m': 250,
        'sim_time_s': PROFILE_SECONDS,
        'warmup_epochs_excluded': WARMUP_EPOCHS,
        'trace_sources': {str(size): str(path) for size, path in TRACE_ROOTS.items()},
        'cpu_model': cpu_model(),
        'logical_cpu_count': os.cpu_count(),
        'memory_bytes': memory_bytes(),
        'python': sys.version,
        'operating_system': platform.platform(),
        'execution': 'one CPU process at a time; no GPU acceleration',
        'timing_clock': 'time.perf_counter_ns',
        'timing_definitions': {
            'ch_ms': 'recluster entry through the start of backbone plan; includes '
                     'prediction, TLET, CH scoring/election, membership and relay hold',
            'bb_ms': 'BackbonePlanner.plan, including graph construction and Dijkstra',
            'path_ms': 'sum of BackbonePlanner._dijkstra calls inside the epoch',
            'path_calls': 'number of BackbonePlanner._dijkstra calls inside the plan',
            'epoch_ms': 'complete ClusterManager.recluster call, excluding PHY/MAC '
                        'events and the rest of the simulation',
        },
    }


def profile_single(root, size, seed, attempt):
    logging.disable(logging.CRITICAL)
    from experiments.run_experiment import run_once
    from topology.mwmp_dca.backbone_planner import BackbonePlanner
    from topology.mwmp_dca.cluster_manager import ClusterManager

    original_recluster = ClusterManager.recluster
    original_plan = BackbonePlanner.plan
    original_dijkstra = BackbonePlanner._dijkstra
    active = None
    in_plan = False
    epochs = []

    def measured_recluster(manager):
        nonlocal active
        if active is not None:
            raise RuntimeError('Nested clustering epoch')
        active = {'start_ns': time.perf_counter_ns(), 'path_ns': 0,
                  'path_calls': 0}
        try:
            return original_recluster(manager)
        finally:
            end_ns = time.perf_counter_ns()
            if 'ch_ns' not in active or 'bb_ns' not in active:
                raise RuntimeError('Clustering epoch did not call backbone plan')
            epochs.append({
                'epoch': manager.round_counter,
                'ch_ms': active['ch_ns'] / 1e6,
                'bb_ms': active['bb_ns'] / 1e6,
                'path_ms': active['path_ns'] / 1e6,
                'path_calls': active['path_calls'],
                'epoch_ms': (end_ns - active['start_ns']) / 1e6,
            })
            active = None

    def measured_plan(planner, *args, **kwargs):
        nonlocal in_plan
        if active is None:
            return original_plan(planner, *args, **kwargs)
        active['ch_ns'] = time.perf_counter_ns() - active['start_ns']
        started_ns = time.perf_counter_ns()
        in_plan = True
        try:
            return original_plan(planner, *args, **kwargs)
        finally:
            active['bb_ns'] = time.perf_counter_ns() - started_ns
            in_plan = False

    def measured_dijkstra(planner, *args, **kwargs):
        started_ns = time.perf_counter_ns()
        try:
            return original_dijkstra(planner, *args, **kwargs)
        finally:
            if active is not None and in_plan:
                active['path_ns'] += time.perf_counter_ns() - started_ns
                active['path_calls'] += 1

    ClusterManager.recluster = measured_recluster
    BackbonePlanner.plan = measured_plan
    BackbonePlanner._dijkstra = measured_dijkstra
    directory = root / f'n{size}' / f'seed{seed}' / f'attempt{attempt}'
    directory.mkdir(parents=True, exist_ok=False)
    trace = trace_path(size, seed).resolve()
    if not trace.is_file():
        raise FileNotFoundError(trace)
    try:
        run_once(
            protocol='DSDV', seed=seed, n_drones=size,
            output_dir=str(directory / 'simulation'), speed=15.0,
            experiment_name=f'e10_proposed_n{size}_seed{seed}',
            predictor_mode='kinematic', traffic_rate=2.0, comm_range=250.0,
            sim_time_s=PROFILE_SECONDS, method='PROPOSED',
            mobility_trace_mode='replay', mobility_trace_file=str(trace),
            packet_diagnostics=False,
        )
    finally:
        ClusterManager.recluster = original_recluster
        BackbonePlanner.plan = original_plan
        BackbonePlanner._dijkstra = original_dijkstra
    selected = epochs[WARMUP_EPOCHS:]
    if len(selected) < 2:
        raise RuntimeError(f'Insufficient profiling epochs: {len(epochs)}')
    for row in epochs:
        if not all(math.isfinite(row[key]) and row[key] >= 0 for key in
                   ('ch_ms', 'bb_ms', 'path_ms', 'epoch_ms')):
            raise RuntimeError('Invalid timing value')
        if row['path_ms'] > row['bb_ms'] or row['ch_ms'] + row['bb_ms'] > row['epoch_ms']:
            raise RuntimeError('Timing intervals do not nest')
    with (directory / 'epochs.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(epochs[0]))
        writer.writeheader()
        writer.writerows(epochs)
    summary = {
        'size': size, 'seed': seed, 'epoch_count': len(epochs),
        'measured_epoch_count': len(selected),
        'trace_path': str(trace),
    }
    for key in ('ch_ms', 'bb_ms', 'path_ms', 'epoch_ms'):
        summary[key] = statistics.mean(row[key] for row in selected)
    summary['path_calls'] = statistics.mean(row['path_calls'] for row in selected)
    (directory / 'summary.json').write_text(
        json.dumps(summary, indent=2), encoding='utf-8'
    )


def completed_attempt(root, size, seed):
    parent = root / f'n{size}' / f'seed{seed}'
    complete = []
    for path in sorted(parent.glob('attempt*')):
        summary = path / 'summary.json'
        epochs = path / 'epochs.csv'
        if summary.is_file() and epochs.is_file():
            row = json.loads(summary.read_text(encoding='utf-8'))
            if row['size'] == size and row['seed'] == seed:
                complete.append(row)
    if len(complete) > 1:
        raise RuntimeError(f'Duplicate E10 result for N={size}, seed={seed}')
    return complete[0] if complete else None


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--single', action='store_true')
    parser.add_argument('--size', type=int, choices=SIZES)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--attempt', type=int)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    root = args.output_root.resolve()
    if args.single:
        if args.size is None or args.seed is None or args.attempt is None:
            parser.error('--single requires --size, --seed and --attempt')
        profile_single(root, args.size, args.seed, args.attempt)
        return
    planned = manifest()
    existing = root / 'manifest.json'
    if existing.is_file() and json.loads(existing.read_text(encoding='utf-8')) != planned:
        raise RuntimeError('E10 manifest differs from frozen profiling plan')
    missing = [(size, seed) for size in SIZES for seed in SEEDS
               if completed_attempt(root, size, seed) is None]
    print(json.dumps({'completed': len(SIZES) * len(SEEDS) - len(missing),
                      'missing': missing}), flush=True)
    if args.dry_run:
        return
    root.mkdir(parents=True, exist_ok=True)
    if not existing.is_file():
        existing.write_text(json.dumps(planned, indent=2), encoding='utf-8')
    for size, seed in missing:
        parent = root / f'n{size}' / f'seed{seed}'
        attempts = [int(path.name.removeprefix('attempt'))
                    for path in parent.glob('attempt*')]
        attempt = max(attempts, default=0) + 1
        command = [
            sys.executable, '-m', 'results.run_e10', '--single',
            '--output-root', str(root), '--size', str(size),
            '--seed', str(seed), '--attempt', str(attempt),
        ]
        with (root / f'n{size}_seed{seed}_attempt{attempt}.log').open('w') as stream:
            subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True)
        if completed_attempt(root, size, seed) is None:
            raise RuntimeError(f'E10 child produced no valid summary: N={size}, seed={seed}')
        print(json.dumps({'completed': [size, seed]}), flush=True)
    rows = [completed_attempt(root, size, seed)
            for size in SIZES for seed in SEEDS]
    if any(row is None for row in rows):
        raise RuntimeError('E10 matrix incomplete')
    write_csv(root / 'seed_means.csv', rows)
    group_rows = []
    for size in SIZES:
        group = [row for row in rows if row['size'] == size]
        result = {'size': size, 'seeds': len(group)}
        for key in ('ch_ms', 'bb_ms', 'path_ms', 'epoch_ms'):
            values = [row[key] for row in group]
            result[f'{key}_mean'] = statistics.mean(values)
            result[f'{key}_sd'] = statistics.stdev(values)
        result['path_calls_mean'] = statistics.mean(row['path_calls'] for row in group)
        group_rows.append(result)
    write_csv(root / 'size_summary.csv', group_rows)
    print(json.dumps({'final_runs': len(rows), 'summary': str(root / 'size_summary.csv')}),
          flush=True)


if __name__ == '__main__':
    main()
