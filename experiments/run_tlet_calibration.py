import argparse
import json
import os
import statistics

from experiments.run_experiment import run_sweep
from utils import config


METRICS = (
    'pdr_percent',
    'e2e_delay_ms',
    'routing_load',
    'throughput_kbps',
    'control_packet_total',
    'cluster_head_churn_ratio',
    'mean_cluster_tenure_rounds',
    'mean_ch_tenure_rounds',
    'average_tlet',
    'predictor_rmse',
)


def _summary(rows):
    result = {'runs': len(rows)}
    for metric in METRICS:
        values = [float(row[metric]) for row in rows if row.get(metric) is not None]
        if values:
            result[metric] = {
                'mean': statistics.fmean(values),
                'stdev': statistics.stdev(values) if len(values) > 1 else 0.0,
            }
    return result


def main():
    parser = argparse.ArgumentParser(description='Screen H5/H10 TLET contribution with paired seeds')
    parser.add_argument('--output-dir', default='results/tlet_calibration_20260913')
    parser.add_argument('--seeds', default='3031,3032,3033')
    parser.add_argument('--n-drones', type=int, default=20)
    parser.add_argument('--speed', type=int, default=30)
    parser.add_argument('--comm-range', type=float, default=200)
    parser.add_argument('--sim-time-s', type=float, default=30)
    parser.add_argument('--traffic-rate', type=float, default=2)
    parser.add_argument('--model-device', choices=('cpu', 'auto'), default='cpu')
    parser.add_argument('--variant', default='all', choices=(
        'all', 'h5_full', 'h5_without_tlet', 'h10_full', 'h10_without_tlet'))
    args = parser.parse_args()
    config.MODEL_DEVICE = args.model_device
    seeds = [int(value) for value in args.seeds.split(',')]
    variants = (
        ('h5_full', 5, True, 'models/lstm/candidate_residual.pt', 'models/config/lstm_candidate_residual.json'),
        ('h5_without_tlet', 5, False, 'models/lstm/candidate_residual.pt', 'models/config/lstm_candidate_residual.json'),
        ('h10_full', 10, True, 'models/lstm/candidate_residual_h10.pt', 'models/config/lstm_candidate_residual_h10.json'),
        ('h10_without_tlet', 10, False, 'models/lstm/candidate_residual_h10.pt', 'models/config/lstm_candidate_residual_h10.json'),
    )
    if args.variant != 'all':
        variants = tuple(item for item in variants if item[0] == args.variant)
    summaries = {}
    os.makedirs(args.output_dir, exist_ok=True)
    for name, horizon, use_tlet, model_path, model_config_path in variants:
        config.PREDICTION_HORIZON = horizon
        config.LSTM_MODEL_PATH = model_path
        config.LSTM_CONFIG_PATH = model_config_path
        rows = run_sweep(
            protocol='MWMP_DCA',
            seeds=seeds,
            drone_counts=[args.n_drones],
            output_dir=args.output_dir,
            experiment_name=name,
            speeds=[args.speed],
            predictor_mode='lstm',
            cluster_algorithm='GA_MP_DCA',
            ablation_flags={'USE_TLET': use_tlet},
            traffic_rate=args.traffic_rate,
            comm_range=args.comm_range,
            sim_time_s=args.sim_time_s,
        )
        summaries[name] = _summary(rows)
        print(json.dumps({name: summaries[name]}, indent=2))
    output = {
        'paired_seeds': seeds,
        'n_drones': args.n_drones,
        'speed_mps': args.speed,
        'comm_range_m': args.comm_range,
        'sim_time_s': args.sim_time_s,
        'variants': summaries,
    }
    summary_name = 'tlet_calibration_summary.json' if args.variant == 'all' else f'{args.variant}_summary.json'
    with open(os.path.join(args.output_dir, summary_name), 'w', encoding='utf-8') as stream:
        json.dump(output, stream, indent=2)


if __name__ == '__main__':
    main()
