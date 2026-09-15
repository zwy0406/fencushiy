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
    'average_tlet',
)


def summarize(rows):
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
    parser = argparse.ArgumentParser(description='Screen adaptive GA-MP-DCA stability controls')
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--seeds', default='4101,4102,4103,4104,4105')
    parser.add_argument('--n-drones', type=int, default=20)
    parser.add_argument('--speeds', default='20,40')
    parser.add_argument('--comm-range', type=float, default=200)
    parser.add_argument('--sim-time-s', type=float, default=60)
    parser.add_argument('--traffic-rate', type=float, default=2)
    parser.add_argument('--adaptive', action='store_true')
    parser.add_argument('--backbone-connectors', action='store_true')
    parser.add_argument('--alpha', type=float, default=1.0)
    parser.add_argument('--weight-margin', type=float, default=0.08)
    parser.add_argument('--stable-rounds', type=int, default=3)
    parser.add_argument('--stability-bonus', type=float, default=0.0)
    parser.add_argument('--tlet-gain-margin', type=float, default=0.10)
    parser.add_argument('--score-loss-tolerance', type=float, default=0.02)
    parser.add_argument('--model-device', choices=('cpu', 'auto'), default='cpu')
    args = parser.parse_args()

    config.MODEL_DEVICE = args.model_device
    config.PREDICTION_HORIZON = 5
    config.LSTM_MODEL_PATH = 'models/lstm/candidate_residual.pt'
    config.LSTM_CONFIG_PATH = 'models/config/lstm_candidate_residual.json'
    seeds = [int(value) for value in args.seeds.split(',')]
    speeds = [int(value) for value in args.speeds.split(',')]
    os.makedirs(args.output_dir, exist_ok=True)
    rows = run_sweep(
        protocol='MWMP_DCA',
        seeds=seeds,
        drone_counts=[args.n_drones],
        output_dir=args.output_dir,
        experiment_name=args.name,
        speeds=speeds,
        predictor_mode='lstm',
        cluster_algorithm='GA_MP_DCA',
        ablation_flags={
            'ADAPTIVE_CH_ROTATION': args.adaptive,
            'USE_BACKBONE_CONNECTORS': args.backbone_connectors,
            'TLET_SMOOTHING_ALPHA': args.alpha,
            'CH_ROTATION_WEIGHT_MARGIN': args.weight_margin,
            'CH_ROTATION_STABLE_ROUNDS': args.stable_rounds,
            'CH_ROTATION_STABILITY_MARGIN_BONUS': args.stability_bonus,
            'CH_ROTATION_TLET_GAIN_MARGIN': args.tlet_gain_margin,
            'CH_ROTATION_SCORE_LOSS_TOLERANCE': args.score_loss_tolerance,
        },
        traffic_rate=args.traffic_rate,
        comm_range=args.comm_range,
        sim_time_s=args.sim_time_s,
    )
    output = {
        'name': args.name,
        'seeds': seeds,
        'speeds': speeds,
        'parameters': {
            'adaptive': args.adaptive,
            'backbone_connectors': args.backbone_connectors,
            'alpha': args.alpha,
            'weight_margin': args.weight_margin,
            'stable_rounds': args.stable_rounds,
            'stability_bonus': args.stability_bonus,
            'tlet_gain_margin': args.tlet_gain_margin,
            'score_loss_tolerance': args.score_loss_tolerance,
        },
        'summary': summarize(rows),
    }
    with open(os.path.join(args.output_dir, f'{args.name}_summary.json'), 'w', encoding='utf-8') as stream:
        json.dump(output, stream, indent=2)
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
