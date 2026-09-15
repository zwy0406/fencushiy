import argparse
import os

from experiments.run_experiment import run_sweep
from utils import config


ALGORITHMS = ('MDCS', 'TDC_MOPSO', 'MWMP_DCA', 'GA_MP_DCA')


def main():
    parser = argparse.ArgumentParser(description='Run a short recent-baseline pilot')
    parser.add_argument('--output-dir', default='results/pilot_recent_baselines')
    parser.add_argument('--seeds', default='2025,2026,2027')
    parser.add_argument('--n-drones', type=int, default=20)
    parser.add_argument('--speed', type=int, default=20)
    parser.add_argument('--speeds', default=None)
    parser.add_argument('--sim-time-s', type=float, default=30.0)
    parser.add_argument('--traffic-rate', type=float, default=None)
    parser.add_argument('--comm-range', type=float, default=None)
    parser.add_argument('--algorithms', nargs='+', choices=ALGORITHMS, default=list(ALGORITHMS))
    parser.add_argument('--model-device', choices=('cpu', 'auto'), default='cpu')
    parser.add_argument('--ch-let-drop-ratio', type=float, default=None)
    parser.add_argument('--ga-persistence-bonus', type=float, default=None)
    parser.add_argument('--rotation-weight-margin', type=float, default=None)
    parser.add_argument('--ga-adaptive-stability', action='store_true')
    parser.add_argument('--ga-backbone-connectors', action='store_true')
    parser.add_argument('--ga-relay-hold-rounds', type=int, default=0)
    parser.add_argument('--ga-tlet-alpha', type=float, default=0.35)
    parser.add_argument('--ga-stability-bonus', type=float, default=0.05)
    parser.add_argument('--ga-stable-rounds', type=int, default=3)
    args = parser.parse_args()

    config.MODEL_DEVICE = args.model_device
    if args.ch_let_drop_ratio is not None:
        config.CH_LET_DROP_RATIO = args.ch_let_drop_ratio
    if args.ga_persistence_bonus is not None:
        config.GA_CH_PERSISTENCE_BONUS = args.ga_persistence_bonus
    if args.rotation_weight_margin is not None:
        config.CH_ROTATION_WEIGHT_MARGIN = args.rotation_weight_margin
    os.makedirs(args.output_dir, exist_ok=True)
    seeds = [int(item) for item in args.seeds.split(',')]
    speeds = (
        [int(item) for item in args.speeds.split(',')]
        if args.speeds else [args.speed]
    )
    for algorithm in args.algorithms:
        baseline = algorithm in ('MDCS', 'TDC_MOPSO')
        flags = {
            'ADAPTIVE_CH_ROTATION': False,
            'USE_BACKBONE_CONNECTORS': False,
            'TLET_SMOOTHING_ALPHA': 1.0,
        }
        if baseline:
            flags.update({
                'USE_LSTM_PREDICTOR': False,
                'USE_GAT_FEATURE': False,
                'USE_TLET': False,
                'USE_CH_ROTATION': False,
                'USE_POI_AWARE_WEIGHT': False,
            })
        elif algorithm == 'GA_MP_DCA':
            flags.update({
                'ADAPTIVE_CH_ROTATION': args.ga_adaptive_stability,
                'USE_BACKBONE_CONNECTORS': args.ga_backbone_connectors,
                'BACKBONE_RELAY_HOLD_ROUNDS': args.ga_relay_hold_rounds,
                'TLET_SMOOTHING_ALPHA': args.ga_tlet_alpha,
                'CH_ROTATION_WEIGHT_MARGIN': (
                    args.rotation_weight_margin
                    if args.rotation_weight_margin is not None else 0.10
                ),
                'CH_ROTATION_STABLE_ROUNDS': args.ga_stable_rounds,
                'CH_ROTATION_STABILITY_MARGIN_BONUS': args.ga_stability_bonus,
            })
        run_sweep(
            protocol='MWMP_DCA',
            seeds=seeds,
            drone_counts=[args.n_drones],
            output_dir=args.output_dir,
            experiment_name=f'pilot_{algorithm.lower()}',
            speeds=speeds,
            predictor_mode='kinematic' if baseline else 'lstm',
            cluster_algorithm=algorithm,
            ablation_flags=flags,
            traffic_rate=args.traffic_rate,
            comm_range=args.comm_range,
            sim_time_s=args.sim_time_s,
        )
    print({'status': 'ok', 'output_dir': args.output_dir, 'algorithms': args.algorithms})


if __name__ == '__main__':
    main()
