import argparse
import csv
import itertools
import json
import os

from experiments.run_experiment import run_once
from utils import config


def _candidate_weight_sets():
    space = config.GA_WEIGHT_SEARCH_SPACE
    for combo in itertools.product(
        space['energy'],
        space['link_quality'],
        space['tlet'],
        space['topology'],
        space['mobility'],
    ):
        total = sum(combo)
        if total <= 0:
            continue
        normalized = [value / total for value in combo]
        yield {
            'w1_energy': normalized[0],
            'w2_link_quality': normalized[1],
            'w3_tlet': normalized[2],
            'w4_topology': normalized[3],
            'w5_mobility': normalized[4],
        }


def _write_weight_file(path, weights, source='search'):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({
            'algorithm': 'GA_MP_DCA',
            'scenario': '60UAV_20mps',
            'weights': weights,
            'source': source,
        }, f, indent=2)


def score_result(result):
    pdr = result.get('pdr_percent', 0.0)
    cluster_lifetime = result.get('cluster_lifetime', 0.0)
    connectivity = result.get('connected_ratio', 0.0) * 100.0
    reclustering_penalty = result.get('reclustering_rate', 0.0) * 2.0
    overhead_penalty = result.get('control_packet_total', 0.0) * 0.02
    return pdr + (cluster_lifetime * 2.0) + connectivity - reclustering_penalty - overhead_penalty


def main():
    parser = argparse.ArgumentParser(description='Search GA-MP-DCA score weights')
    parser.add_argument('--output-dir', default='results/weight_search_ga')
    parser.add_argument('--seeds', default='2025,2026')
    parser.add_argument('--n-drones', type=int, default=60)
    parser.add_argument('--speed', type=int, default=20)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    seeds = [int(item) for item in args.seeds.split(',')]
    rows = []
    best_weights = None
    best_score = None
    best_row = None

    original_weight_file = config.GA_WEIGHT_FILE
    temp_weight_file = os.path.join(args.output_dir, 'candidate_weights.json')

    scenarios = [
        {'enable_poi': False, 'poi_count': None, 'poi_speed': None, 'tag': 'no_poi'},
        {'enable_poi': True, 'poi_count': 100, 'poi_speed': 3, 'tag': 'poi'},
    ]

    for candidate_id, weights in enumerate(_candidate_weight_sets(), start=1):
        _write_weight_file(temp_weight_file, weights, source=f'candidate_{candidate_id}')
        config.GA_WEIGHT_FILE = temp_weight_file
        candidate_scores = []

        for scenario in scenarios:
            for seed in seeds:
                result = run_once(
                    protocol='MWMP_DCA',
                    seed=seed,
                    n_drones=args.n_drones,
                    output_dir=args.output_dir,
                    enable_visualization=False,
                    speed=args.speed,
                    enable_poi=scenario['enable_poi'],
                    poi_count=scenario['poi_count'],
                    poi_speed=scenario['poi_speed'],
                    experiment_name=f"ga_weight_search_{candidate_id}_{scenario['tag']}_seed{seed}",
                    predictor_mode='lstm',
                    cluster_algorithm='GA_MP_DCA',
                )
                result['candidate_id'] = candidate_id
                result['scenario'] = scenario['tag']
                result['weights'] = json.dumps(weights, sort_keys=True)
                result['composite_score'] = score_result(result)
                candidate_scores.append(result['composite_score'])
                rows.append(result)

        mean_score = sum(candidate_scores) / len(candidate_scores) if candidate_scores else 0.0
        summary_row = {
            'candidate_id': candidate_id,
            'scenario': 'aggregate',
            'weights': json.dumps(weights, sort_keys=True),
            'composite_score': mean_score,
        }
        rows.append(summary_row)
        if best_score is None or mean_score > best_score:
            best_score = mean_score
            best_weights = weights
            best_row = summary_row

    config.GA_WEIGHT_FILE = original_weight_file
    if best_weights is not None:
        _write_weight_file(config.WEIGHT_SEARCH_OUTPUT_FILE, best_weights, source='weight_search')

    csv_path = os.path.join(args.output_dir, 'weight_search_results.csv')
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print({
        'best_weights': best_weights,
        'best_score': best_score,
        'csv_path': csv_path,
        'selected_weight_file': config.WEIGHT_SEARCH_OUTPUT_FILE,
        'summary': best_row,
    })


if __name__ == '__main__':
    main()
