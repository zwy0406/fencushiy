import argparse
import csv
import itertools
import json
import math
import os
import re
import statistics


EXPERIMENT_RE = re.compile(
    r'^(?P<algorithm>pilot_.+?)_seed(?P<seed>\d+)_n(?P<n_drones>\d+)_v(?P<speed>\d+)$'
)
METRICS = (
    'pdr_percent',
    'throughput_kbps',
    'e2e_delay_ms',
    'routing_load',
    'control_packet_total',
    'cluster_head_churn_ratio',
    'mean_ch_tenure_rounds',
    'mean_cluster_tenure_rounds',
    'mean_backbone_connectivity_ratio',
    'mean_backbone_path_preservation_ratio',
    'mean_bs_reachability_efficiency',
    'connected_backbone_stability_index',
    'usable_ch_tenure_rounds',
)

SOURCE_METRICS = tuple(
    metric for metric in METRICS
    if metric not in ('connected_backbone_stability_index', 'usable_ch_tenure_rounds')
)


def load_rows(root):
    rows = {}
    for directory, _, filenames in os.walk(root):
        for filename in filenames:
            if not filename.endswith('_summary.csv') or '_seed' not in filename:
                continue
            path = os.path.join(directory, filename)
            with open(path, newline='', encoding='utf-8') as stream:
                source_rows = list(csv.DictReader(stream))
            if not source_rows:
                continue
            source = source_rows[0]
            match = EXPERIMENT_RE.match(source.get('experiment', ''))
            if not match:
                continue
            key = (
                match.group('algorithm'),
                int(match.group('seed')),
                int(match.group('speed')),
            )
            parsed = {'source': path}
            for metric in SOURCE_METRICS:
                value = source.get(metric)
                parsed[metric] = float(value) if value not in (None, '') else None
            preservation = parsed.get('mean_backbone_path_preservation_ratio')
            churn = parsed.get('cluster_head_churn_ratio')
            tenure = parsed.get('mean_ch_tenure_rounds')
            parsed['connected_backbone_stability_index'] = (
                preservation * (1.0 - churn)
                if preservation is not None and churn is not None else None
            )
            parsed['usable_ch_tenure_rounds'] = (
                preservation * tenure
                if preservation is not None and tenure is not None else None
            )
            rows[key] = parsed
    return rows


def sign_flip_pvalue(differences):
    if not differences:
        return 1.0
    observed = abs(statistics.fmean(differences))
    extreme = 0
    total = 0
    for signs in itertools.product((-1.0, 1.0), repeat=len(differences)):
        permuted = abs(statistics.fmean(
            value * sign for value, sign in zip(differences, signs)
        ))
        total += 1
        if permuted >= observed - 1e-12:
            extreme += 1
    return extreme / total


def holm_adjust(rows):
    ordered = sorted(enumerate(rows), key=lambda item: item[1]['p_value'])
    running = 0.0
    for rank, (original_idx, row) in enumerate(ordered):
        adjusted = min(1.0, (len(rows) - rank) * row['p_value'])
        running = max(running, adjusted)
        rows[original_idx]['p_holm'] = running


def analyze(rows, proposed, baselines):
    seeds = sorted({key[1] for key in rows})
    speeds = sorted({key[2] for key in rows})
    output = []
    for baseline in baselines:
        for speed in speeds:
            family = []
            for metric in METRICS:
                pairs = []
                for seed in seeds:
                    proposed_row = rows.get((proposed, seed, speed))
                    baseline_row = rows.get((baseline, seed, speed))
                    if not proposed_row or not baseline_row:
                        continue
                    if proposed_row[metric] is None or baseline_row[metric] is None:
                        continue
                    pairs.append((proposed_row[metric], baseline_row[metric]))
                if not pairs:
                    continue
                differences = [left - right for left, right in pairs]
                mean_difference = statistics.fmean(differences)
                difference_std = statistics.stdev(differences) if len(differences) > 1 else 0.0
                baseline_mean = statistics.fmean(right for _, right in pairs)
                family.append({
                    'proposed': proposed,
                    'baseline': baseline,
                    'speed': speed,
                    'metric': metric,
                    'pairs': len(pairs),
                    'proposed_mean': statistics.fmean(left for left, _ in pairs),
                    'baseline_mean': baseline_mean,
                    'mean_difference': mean_difference,
                    'relative_difference_percent': (
                        mean_difference / baseline_mean * 100.0
                        if abs(baseline_mean) > 1e-12 else None
                    ),
                    'difference_ci95': (
                        1.96 * difference_std / math.sqrt(len(differences))
                        if len(differences) > 1 else 0.0
                    ),
                    'cohens_dz': (
                        mean_difference / difference_std
                        if difference_std > 1e-12 else None
                    ),
                    'p_value': sign_flip_pvalue(differences),
                })
            holm_adjust(family)
            output.extend(family)
    return output


def main():
    parser = argparse.ArgumentParser(description='Exact paired comparison for FANET experiments')
    parser.add_argument('--root', required=True)
    parser.add_argument('--proposed', default='pilot_ga_mp_dca')
    parser.add_argument(
        '--baselines',
        default='pilot_mwmp_dca,pilot_mdcs,pilot_tdc_mopso',
    )
    args = parser.parse_args()
    rows = load_rows(args.root)
    comparisons = analyze(
        rows,
        args.proposed,
        [item for item in args.baselines.split(',') if item],
    )
    json_path = os.path.join(args.root, 'paired_comparison.json')
    csv_path = os.path.join(args.root, 'paired_comparison.csv')
    with open(json_path, 'w', encoding='utf-8') as stream:
        json.dump({'unique_runs': len(rows), 'comparisons': comparisons}, stream, indent=2)
    with open(csv_path, 'w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=sorted({key for row in comparisons for key in row}),
        )
        writer.writeheader()
        writer.writerows(comparisons)
    print({'unique_runs': len(rows), 'comparisons': len(comparisons), 'json': json_path, 'csv': csv_path})


if __name__ == '__main__':
    main()
