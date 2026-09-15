import argparse
import os

from experiments.run_experiment import run_sweep
from utils import config


PAPER_BASELINES = ['MDCS', 'TDC_MOPSO', 'MWMP_DCA', 'GA_MP_DCA']
CORE_COMPARE = ['MDCS', 'TDC_MOPSO', 'MWMP_DCA', 'GA_MP_DCA']


def _run_algorithm_matrix(output_dir, experiment_prefix, seeds, algorithms, drone_counts, speeds,
                          enable_poi=False, poi_counts=None, poi_speeds=None, predictor_mode='lstm', ablation_flags=None):
    results = []
    for algorithm in algorithms:
        flags = dict(ablation_flags or {})
        protocol = 'MWMP_DCA'
        if algorithm == 'DSDV':
            protocol = 'DSDV'
        algo_predictor = predictor_mode
        if algorithm in ('LOWEST_ID', 'LEACH_UAV', 'KMEANS', 'MDCS', 'TDC_MOPSO'):
            algo_predictor = 'kinematic'
        if algorithm in ('MDCS', 'TDC_MOPSO'):
            flags.update({
                'USE_LSTM_PREDICTOR': False,
                'USE_GAT_FEATURE': False,
                'USE_TLET': False,
                'USE_CH_ROTATION': False,
                'USE_POI_AWARE_WEIGHT': False,
            })
        results.extend(run_sweep(
            protocol=protocol,
            seeds=seeds,
            drone_counts=drone_counts,
            output_dir=output_dir,
            experiment_name=f'{experiment_prefix}_{algorithm.lower()}',
            speeds=speeds,
            enable_poi=enable_poi,
            poi_counts=poi_counts,
            poi_speeds=poi_speeds,
            weight_profile=config.MWMP_WEIGHT_PROFILE,
            predictor_mode=algo_predictor,
            cluster_algorithm=None if protocol == 'DSDV' else algorithm,
            ablation_flags=flags,
        ))
    return results


def run_e1(output_dir, seeds):
    return _run_algorithm_matrix(
        output_dir=output_dir,
        experiment_prefix='E1_cluster_stability',
        seeds=seeds,
        algorithms=PAPER_BASELINES,
        drone_counts=[60],
        speeds=[20],
    )


def run_e2(output_dir, seeds):
    return _run_algorithm_matrix(
        output_dir=output_dir,
        experiment_prefix='E2_network_scale',
        seeds=seeds,
        algorithms=CORE_COMPARE,
        drone_counts=config.UAV_COUNT_LIST,
        speeds=[20],
    )


def run_e3(output_dir, seeds):
    return _run_algorithm_matrix(
        output_dir=output_dir,
        experiment_prefix='E3_high_speed',
        seeds=seeds,
        algorithms=CORE_COMPARE,
        drone_counts=[60],
        speeds=config.UAV_SPEED_LIST,
    )


def run_e4(output_dir, seeds):
    return _run_algorithm_matrix(
        output_dir=output_dir,
        experiment_prefix='E4_dynamic_poi',
        seeds=seeds,
        algorithms=CORE_COMPARE,
        drone_counts=[60],
        speeds=[20],
        enable_poi=True,
        poi_counts=config.POI_COUNT_LIST,
        poi_speeds=config.POI_SPEED_LIST,
    )


def run_e5(output_dir, seeds):
    return _run_algorithm_matrix(
        output_dir=output_dir,
        experiment_prefix='E5_energy',
        seeds=seeds,
        algorithms=CORE_COMPARE,
        drone_counts=[60],
        speeds=[10, 20, 30],
    )


def run_e6(output_dir, seeds):
    return _run_algorithm_matrix(
        output_dir=output_dir,
        experiment_prefix='E6_control_overhead',
        seeds=seeds,
        algorithms=['DSDV', 'MWMP_DCA', 'GA_MP_DCA'],
        drone_counts=[60],
        speeds=[20],
        enable_poi=True,
        poi_counts=[100],
        poi_speeds=[3],
    )


def run_e7(output_dir, seeds):
    results = []
    ablations = {
        'E7_full': {},
        'E7_without_gat': {'USE_GAT_FEATURE': False},
        'E7_without_lstm': {'USE_LSTM_PREDICTOR': False},
        'E7_without_let': {'USE_TLET': False},
        'E7_without_timer': {'USE_BACKOFF_ELECTION': False},
    }
    for experiment_name, flags in ablations.items():
        predictor_mode = 'kinematic' if flags.get('USE_LSTM_PREDICTOR') is False else 'lstm'
        results.extend(run_sweep(
            protocol='MWMP_DCA',
            seeds=seeds,
            drone_counts=[60],
            output_dir=output_dir,
            experiment_name=experiment_name,
            speeds=[20],
            enable_poi=True,
            poi_counts=[100],
            poi_speeds=[3],
            weight_profile=config.MWMP_WEIGHT_PROFILE,
            predictor_mode=predictor_mode,
            cluster_algorithm='GA_MP_DCA',
            ablation_flags=flags,
        ))
    return results


def run_e8(output_dir, seeds):
    results = []
    results.extend(run_sweep(
        protocol='MWMP_DCA',
        seeds=seeds,
        drone_counts=[60],
        output_dir=output_dir,
        experiment_name='E8_mwmp_kinematic',
        speeds=[20],
        weight_profile=config.MWMP_WEIGHT_PROFILE,
        predictor_mode='kinematic',
        cluster_algorithm='MWMP_DCA',
    ))
    results.extend(run_sweep(
        protocol='MWMP_DCA',
        seeds=seeds,
        drone_counts=[60],
        output_dir=output_dir,
        experiment_name='E8_mwmp_lstm',
        speeds=[20],
        weight_profile=config.MWMP_WEIGHT_PROFILE,
        predictor_mode='lstm',
        cluster_algorithm='MWMP_DCA',
    ))
    results.extend(run_sweep(
        protocol='MWMP_DCA',
        seeds=seeds,
        drone_counts=[60],
        output_dir=output_dir,
        experiment_name='E8_ga_without_gat',
        speeds=[20],
        weight_profile=config.MWMP_WEIGHT_PROFILE,
        predictor_mode='lstm',
        cluster_algorithm='GA_MP_DCA',
        ablation_flags={'USE_GAT_FEATURE': False},
    ))
    results.extend(run_sweep(
        protocol='MWMP_DCA',
        seeds=seeds,
        drone_counts=[60],
        output_dir=output_dir,
        experiment_name='E8_ga_full',
        speeds=[20],
        weight_profile=config.MWMP_WEIGHT_PROFILE,
        predictor_mode='lstm',
        cluster_algorithm='GA_MP_DCA',
    ))
    return results


EXPERIMENT_MAP = {
    'E1': run_e1,
    'E2': run_e2,
    'E3': run_e3,
    'E4': run_e4,
    'E5': run_e5,
    'E6': run_e6,
    'E7': run_e7,
    'E8': run_e8,
}


def main():
    parser = argparse.ArgumentParser(description='Run the GA-MP-DCA experiment study')
    parser.add_argument('--experiment', choices=list(EXPERIMENT_MAP.keys()) + ['ALL'], default='ALL')
    parser.add_argument('--output-dir', default='results/study_ga_mp_dca')
    parser.add_argument('--seeds', default='2025,2026,2027')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    seeds = [int(item) for item in args.seeds.split(',')]

    if args.experiment == 'ALL':
        for experiment_id in ['E1', 'E2', 'E3', 'E4', 'E5', 'E6', 'E7', 'E8']:
            EXPERIMENT_MAP[experiment_id](args.output_dir, seeds)
    else:
        EXPERIMENT_MAP[args.experiment](args.output_dir, seeds)

    print({'status': 'ok', 'output_dir': args.output_dir, 'experiment': args.experiment})


if __name__ == '__main__':
    main()
