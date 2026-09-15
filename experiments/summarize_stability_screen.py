import argparse
import csv
import json
import math
import os
import re
import statistics


EXPERIMENT_RE = re.compile(
    r'^(?P<variant>.+?)(?:_s\d+)?_seed(?P<seed>\d+)_n(?P<n_drones>\d+)_v(?P<speed>\d+)$'
)
METRICS = (
    'pdr_percent',
    'throughput_kbps',
    'e2e_delay_ms',
    'routing_load',
    'connected_ratio',
    'mean_backbone_connectivity_ratio',
    'mean_bs_reachability_ratio',
    'mean_backbone_path_preservation_ratio',
    'mean_bs_reachability_efficiency',
    'backbone_partition_ratio',
    'control_packet_total',
    'cluster_head_churn_ratio',
    'reclustering_rate',
    'mean_cluster_tenure_rounds',
    'mean_ch_tenure_rounds',
)


def load_rows(root):
    deduped = {}
    duplicate_count = 0
    for directory, _, filenames in os.walk(root):
        for filename in filenames:
            if not filename.endswith('_summary.csv') or '_seed' not in filename:
                continue
            path = os.path.join(directory, filename)
            with open(path, newline='', encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream))
            if not rows:
                continue
            row = rows[0]
            match = EXPERIMENT_RE.match(row.get('experiment', ''))
            if not match:
                continue
            variant = match.group('variant')
            seed = int(match.group('seed'))
            speed = int(match.group('speed'))
            key = (variant, seed, speed)
            if key in deduped:
                duplicate_count += 1
                continue
            parsed = {
                'variant': variant,
                'seed': seed,
                'speed': speed,
                'source': path,
            }
            for metric in METRICS:
                value = row.get(metric)
                parsed[metric] = float(value) if value not in (None, '') else None
            deduped[key] = parsed
    return list(deduped.values()), duplicate_count


def aggregate(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault((row['variant'], row['speed']), []).append(row)

    output = []
    for (variant, speed), samples in sorted(grouped.items()):
        result = {
            'variant': variant,
            'speed': speed,
            'runs': len(samples),
        }
        for metric in METRICS:
            values = [row[metric] for row in samples if row[metric] is not None]
            if not values:
                continue
            result[f'{metric}_mean'] = statistics.fmean(values)
            result[f'{metric}_std'] = statistics.stdev(values) if len(values) > 1 else 0.0
            result[f'{metric}_ci95'] = (
                1.96 * statistics.stdev(values) / math.sqrt(len(values))
                if len(values) > 1 else 0.0
            )
        output.append(result)
    return output


def paired_rank(rows, baseline_variant):
    by_key = {(row['variant'], row['seed'], row['speed']): row for row in rows}
    variants = sorted({row['variant'] for row in rows if row['variant'] != baseline_variant})
    speeds = sorted({row['speed'] for row in rows})
    ranking = []
    for variant in variants:
        pairs = []
        for speed in speeds:
            for seed in sorted({row['seed'] for row in rows}):
                baseline = by_key.get((baseline_variant, seed, speed))
                candidate = by_key.get((variant, seed, speed))
                if baseline and candidate:
                    pairs.append((baseline, candidate))
        if not pairs:
            continue

        deltas = {}
        for metric in METRICS:
            values = [
                candidate[metric] - baseline[metric]
                for baseline, candidate in pairs
                if baseline[metric] is not None and candidate[metric] is not None
            ]
            if values:
                deltas[metric] = statistics.fmean(values)

        speed_pdr_deltas = {}
        for speed in speeds:
            values = [
                candidate['pdr_percent'] - baseline['pdr_percent']
                for baseline, candidate in pairs
                if candidate['speed'] == speed
            ]
            if values:
                speed_pdr_deltas[str(speed)] = statistics.fmean(values)
        eligible = bool(speed_pdr_deltas) and min(speed_pdr_deltas.values()) >= -1.0

        churn_improvements = []
        tenure_improvements = []
        connectivity_improvements = []
        for baseline, candidate in pairs:
            if baseline['cluster_head_churn_ratio']:
                churn_improvements.append(
                    (baseline['cluster_head_churn_ratio'] - candidate['cluster_head_churn_ratio']) /
                    baseline['cluster_head_churn_ratio']
                )
            if baseline['mean_ch_tenure_rounds']:
                tenure_improvements.append(
                    (candidate['mean_ch_tenure_rounds'] - baseline['mean_ch_tenure_rounds']) /
                    baseline['mean_ch_tenure_rounds']
                )
            if baseline['connected_ratio']:
                connectivity_improvements.append(
                    (candidate['connected_ratio'] - baseline['connected_ratio']) /
                    baseline['connected_ratio']
                )
        stability_score = (
            0.50 * statistics.fmean(churn_improvements or [0.0]) +
            0.35 * statistics.fmean(tenure_improvements or [0.0]) +
            0.15 * statistics.fmean(connectivity_improvements or [0.0])
        )
        ranking.append({
            'variant': variant,
            'paired_runs': len(pairs),
            'eligible': eligible,
            'stability_score': stability_score,
            'pdr_delta_by_speed': speed_pdr_deltas,
            'mean_deltas': deltas,
        })
    return sorted(
        ranking,
        key=lambda row: (row['eligible'], row['stability_score'], row['mean_deltas'].get('pdr_percent', -999.0)),
        reverse=True,
    )


def main():
    parser = argparse.ArgumentParser(description='Aggregate and rank split stability-screen results')
    parser.add_argument('--root', required=True)
    parser.add_argument('--baseline', default='legacy_a100')
    parser.add_argument('--output', default=None)
    args = parser.parse_args()

    rows, duplicate_count = load_rows(args.root)
    report = {
        'root': args.root,
        'unique_runs': len(rows),
        'duplicates_ignored': duplicate_count,
        'aggregate': aggregate(rows),
        'ranking': paired_rank(rows, args.baseline),
    }
    output_path = args.output or os.path.join(args.root, 'stability_screen_summary.json')
    with open(output_path, 'w', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
