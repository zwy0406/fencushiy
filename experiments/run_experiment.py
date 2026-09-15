import argparse
import csv
import math
import os
import statistics
import time
import simpy
from utils import config
from simulator.simulator import Simulator


def reset_packet_ids():
    config.GL_ID_DATA_PACKET = 0
    config.GL_ID_HELLO_PACKET = 10000
    config.GL_ID_ACK_PACKET = 20000
    config.GL_ID_VF_PACKET = 30000
    config.GL_ID_GRAD_MESSAGE = 40000


def reset_experiment_flags():
    config.CLUSTER_ALGORITHM = 'MWMP_DCA'
    config.PREDICTOR_MODE = 'kinematic'
    config.DATA_PACKET_RATE = 5
    config.USE_LSTM_PREDICTOR = True
    config.USE_GAT_FEATURE = True
    config.USE_TLET = True
    config.USE_MOBILITY_FACTOR = True
    config.USE_HYBRID_WEIGHT = True
    config.USE_BACKOFF_ELECTION = True
    config.USE_CH_ROTATION = True
    config.USE_BACKBONE_CONNECTORS = False
    config.ADAPTIVE_CH_ROTATION = False
    config.TLET_SMOOTHING_ALPHA = 1.0
    config.CH_ROTATION_WEIGHT_MARGIN = 0.08
    config.CH_ROTATION_STABLE_ROUNDS = 3
    config.CH_ROTATION_STABILITY_MARGIN_BONUS = 0.0
    config.CH_ROTATION_TLET_GAIN_MARGIN = 0.10
    config.CH_ROTATION_SCORE_LOSS_TOLERANCE = 0.02
    config.GA_CH_PERSISTENCE_BONUS = 0.0
    config.USE_POI_AWARE_WEIGHT = True


def run_once(protocol, seed, n_drones, output_dir, enable_visualization=False, speed=None,
             enable_poi=None, poi_count=None, poi_speed=None, experiment_name=None,
             weight_profile=None, predictor_mode=None, cluster_algorithm=None, ablation_flags=None,
             traffic_rate=None, comm_range=None, sim_time_s=None):
    requested_predictor_mode = predictor_mode or config.PREDICTOR_MODE
    requested_cluster_algorithm = cluster_algorithm or ('DSDV' if protocol == 'DSDV' else config.CLUSTER_ALGORITHM)
    config.ROUTING_PROTOCOL = protocol
    config.NUMBER_OF_DRONES = n_drones
    config.MAX_TTL = n_drones + 1
    config.ENABLE_VISUALIZATION = enable_visualization
    config.ENABLE_PLOTS = enable_visualization
    config.EXPERIMENT_NAME = experiment_name or f'{protocol.lower()}_seed{seed}_n{n_drones}'
    config.RESULTS_DIR = output_dir
    config.ENABLE_POI = False
    config.DEFAULT_UAV_SPEED = 10
    config.MODEL_STATUS = {'lstm': 'disabled', 'gat': 'disabled', 'ga_mode': 'inactive'}
    for dirname in [
        config.RESULTS_METRICS_DIRNAME,
        config.RESULTS_FIGURES_DIRNAME,
        config.RESULTS_LOGS_DIRNAME,
        config.RESULTS_MODELS_DIRNAME,
    ]:
        os.makedirs(os.path.join(output_dir, dirname), exist_ok=True)
    reset_experiment_flags()
    if enable_poi is not None:
        config.ENABLE_POI = enable_poi
    if poi_count is not None:
        config.POI_COUNT = poi_count
    if poi_speed is not None:
        config.POI_SPEED_LIST = [poi_speed]
    if speed is not None:
        config.HETEROGENEOUS = 0
        config.DEFAULT_UAV_SPEED = speed
        config.UAV_SPEED_LIST = [speed]
    if traffic_rate is not None:
        config.DATA_PACKET_RATE = traffic_rate
    if comm_range is not None:
        config.COMMUNICATION_RANGE = comm_range
    if sim_time_s is not None:
        config.SIM_TIME = int(sim_time_s * 1e6)
    if weight_profile is not None:
        config.MWMP_WEIGHT_PROFILE = weight_profile
    if predictor_mode is not None:
        config.PREDICTOR_MODE = predictor_mode
    if cluster_algorithm is not None:
        config.CLUSTER_ALGORITHM = cluster_algorithm
    ablation_flags = ablation_flags or {}
    for key, value in ablation_flags.items():
        setattr(config, key, value)
    reset_packet_ids()

    env = simpy.Environment()
    channel_states = {i: simpy.Resource(env, capacity=1) for i in range(config.NUMBER_OF_DRONES)}
    sim = Simulator(seed=seed, env=env, channel_states=channel_states, n_drones=config.NUMBER_OF_DRONES)
    started_at = time.perf_counter()
    env.run(until=config.SIM_TIME)
    wall_clock_s = time.perf_counter() - started_at
    summary = sim.metrics.collect_summary()
    summary['wall_clock_s'] = wall_clock_s
    if speed is not None:
        summary['uav_speed_mps'] = speed
    if poi_count is not None:
        summary['poi_count'] = poi_count
    if poi_speed is not None:
        summary['poi_speed_mps'] = poi_speed
    if weight_profile is not None:
        summary['weight_profile'] = weight_profile
    if traffic_rate is not None:
        summary['traffic_rate_pps'] = traffic_rate
    if comm_range is not None:
        summary['comm_range_m'] = comm_range
    if sim_time_s is not None:
        summary['sim_time_s'] = sim_time_s
    summary['predictor_mode'] = config.PREDICTOR_MODE
    summary['predictor_mode_requested'] = requested_predictor_mode
    summary['cluster_algorithm'] = config.CLUSTER_ALGORITHM
    summary['cluster_algorithm_requested'] = requested_cluster_algorithm
    summary['use_lstm_predictor'] = config.USE_LSTM_PREDICTOR
    summary['use_gat_feature'] = config.USE_GAT_FEATURE
    summary['use_tlet'] = config.USE_TLET
    summary['use_mobility_factor'] = config.USE_MOBILITY_FACTOR
    summary['use_hybrid_weight'] = config.USE_HYBRID_WEIGHT
    summary['use_backoff_election'] = config.USE_BACKOFF_ELECTION
    summary['use_ch_rotation'] = config.USE_CH_ROTATION
    summary['use_backbone_connectors'] = config.USE_BACKBONE_CONNECTORS
    summary['adaptive_ch_rotation'] = config.ADAPTIVE_CH_ROTATION
    summary['tlet_smoothing_alpha'] = config.TLET_SMOOTHING_ALPHA
    summary['ch_rotation_weight_margin'] = config.CH_ROTATION_WEIGHT_MARGIN
    summary['ch_rotation_stable_rounds'] = config.CH_ROTATION_STABLE_ROUNDS
    summary['ch_rotation_stability_margin_bonus'] = config.CH_ROTATION_STABILITY_MARGIN_BONUS
    summary['ch_rotation_tlet_gain_margin'] = config.CH_ROTATION_TLET_GAIN_MARGIN
    summary['ch_rotation_score_loss_tolerance'] = config.CH_ROTATION_SCORE_LOSS_TOLERANCE
    summary['use_poi_aware_weight'] = config.USE_POI_AWARE_WEIGHT
    summary['mobility_model'] = config.MOBILITY_MODEL
    summary['traffic_rate_pps'] = config.DATA_PACKET_RATE
    summary['model_status_lstm'] = config.MODEL_STATUS.get('lstm')
    summary['model_status_gat'] = config.MODEL_STATUS.get('gat')
    summary['ga_mode_status'] = config.MODEL_STATUS.get('ga_mode')
    summary['ga_weight_file'] = config.GA_WEIGHT_FILE
    return summary


def write_batch_results(output_dir, experiment_name, results):
    if not results:
        return None
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, f'{experiment_name}_batch.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    return csv_path


def write_group_summary(output_dir, experiment_name, results):
    if not results:
        return None

    group_keys = ['protocol', 'number_of_drones', 'uav_speed_mps', 'poi_count', 'poi_speed_mps',
                  'weight_profile', 'predictor_mode', 'cluster_algorithm', 'use_lstm_predictor', 'use_gat_feature',
                  'use_tlet', 'use_mobility_factor', 'use_hybrid_weight', 'use_backoff_election',
                  'use_ch_rotation', 'use_poi_aware_weight', 'mobility_model', 'model_status_lstm', 'model_status_gat']
    numeric_keys = [key for key, value in results[0].items() if isinstance(value, (int, float))]
    grouped = {}

    for row in results:
        key = tuple(row.get(name) for name in group_keys)
        grouped.setdefault(key, []).append(row)

    summary_rows = []
    for key, rows in grouped.items():
        summary = {name: key[idx] for idx, name in enumerate(group_keys)}
        summary['runs'] = len(rows)
        for metric in numeric_keys:
            values = [float(item[metric]) for item in rows if metric in item]
            if not values:
                continue
            summary[f'{metric}_mean'] = statistics.mean(values)
            summary[f'{metric}_std'] = statistics.stdev(values) if len(values) > 1 else 0.0
            summary[f'{metric}_ci95'] = (
                1.96 * statistics.stdev(values) / math.sqrt(len(values))
                if len(values) > 1 else 0.0
            )
        summary_rows.append(summary)

    csv_path = os.path.join(output_dir, f'{experiment_name}_group_summary.csv')
    fieldnames = sorted({field for row in summary_rows for field in row.keys()})
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)
    _plot_group_summary(summary_rows, output_dir, experiment_name)
    return csv_path


def _plot_group_summary(rows, output_dir, experiment_name):
    if not rows:
        return
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return

    figures_dir = os.path.join(output_dir, config.RESULTS_FIGURES_DIRNAME)
    os.makedirs(figures_dir, exist_ok=True)
    metrics = [
        ('pdr_percent_mean', 'PDR (%)'),
        ('throughput_kbps_mean', 'Throughput (kbps)'),
        ('cluster_lifetime_mean', 'Cluster Lifetime'),
        ('control_packet_total_mean', 'Control Overhead'),
    ]
    labels = [row.get('cluster_algorithm') or row.get('protocol') or f'row{idx+1}' for idx, row in enumerate(rows)]
    for metric_key, ylabel in metrics:
        values = []
        for row in rows:
            value = row.get(metric_key)
            if value is None:
                values.append(0.0)
            else:
                values.append(float(value))
        plt.figure(figsize=(max(6, len(labels) * 1.2), 4))
        plt.bar(labels, values)
        plt.ylabel(ylabel)
        plt.xticks(rotation=20, ha='right')
        plt.tight_layout()
        plt.savefig(os.path.join(figures_dir, f'{experiment_name}_{metric_key}.png'))
        plt.close()


def run_sweep(protocol, seeds, drone_counts, output_dir, experiment_name, speeds=None,
              enable_poi=False, poi_counts=None, poi_speeds=None, weight_profile=None,
              predictor_mode=None, cluster_algorithm=None, ablation_flags=None, traffic_rate=None,
              comm_range=None, sim_time_s=None):
    results = []
    speeds = speeds or [None]
    poi_counts = poi_counts or [None]
    poi_speeds = poi_speeds or [None]
    experiment_dir = os.path.join(output_dir, experiment_name)
    os.makedirs(experiment_dir, exist_ok=True)

    for seed in seeds:
        for n_drones in drone_counts:
            for speed in speeds:
                for poi_count in poi_counts:
                    for poi_speed in poi_speeds:
                        scenario_name = f'{experiment_name}_seed{seed}_n{n_drones}'
                        if speed is not None:
                            scenario_name += f'_v{speed}'
                        if poi_count is not None:
                            scenario_name += f'_poi{poi_count}'
                        if poi_speed is not None:
                            scenario_name += f'_pvs{poi_speed}'
                        result = run_once(
                            protocol=protocol,
                            seed=seed,
                            n_drones=n_drones,
                            output_dir=experiment_dir,
                            enable_visualization=False,
                            speed=speed,
                            enable_poi=enable_poi,
                            poi_count=poi_count,
                            poi_speed=poi_speed,
                            experiment_name=scenario_name,
                            weight_profile=weight_profile,
                            predictor_mode=predictor_mode,
                            cluster_algorithm=cluster_algorithm,
                            ablation_flags=ablation_flags,
                            traffic_rate=traffic_rate,
                            comm_range=comm_range,
                            sim_time_s=sim_time_s,
                        )
                        results.append(result)
    write_batch_results(experiment_dir, experiment_name, results)
    write_group_summary(experiment_dir, experiment_name, results)
    return results


def main():
    parser = argparse.ArgumentParser(description='Run a UavNetSim experiment')
    parser.add_argument('--protocol', default='DSDV', choices=['DSDV', 'MWMP_DCA'])
    parser.add_argument('--seed', type=int, default=2025)
    parser.add_argument('--n-drones', type=int, default=config.NUMBER_OF_DRONES)
    parser.add_argument('--output-dir', default='results')
    parser.add_argument('--visualization', action='store_true')
    parser.add_argument('--speed', type=int, default=None)
    parser.add_argument('--enable-poi', action='store_true')
    parser.add_argument('--poi-count', type=int, default=None)
    parser.add_argument('--poi-speed', type=int, default=None)
    parser.add_argument('--experiment-name', default=None)
    parser.add_argument('--weight-profile', default=None, choices=list(config.MWMP_WEIGHT_PROFILES.keys()))
    parser.add_argument('--predictor-mode', default=None, choices=['kinematic', 'lstm'])
    parser.add_argument('--cluster-algorithm', default=None, choices=[
        'MWMP_DCA', 'GA_MP_DCA', 'MDCS', 'TDC_MOPSO',
        'LEACH_UAV', 'LOWEST_ID', 'KMEANS', 'MLSC', 'WCA', 'MOBIC',
    ])
    parser.add_argument('--traffic-rate', type=float, default=None, help='Poisson traffic rate (packets/s/UAV)')
    parser.add_argument('--comm-range', type=float, default=None, help='Communication range in meters')
    parser.add_argument('--sim-time-s', type=float, default=None, help='Simulation time in seconds')
    parser.add_argument('--batch-mode', action='store_true')
    parser.add_argument('--seeds', default=None, help='Comma-separated seeds, e.g. 2025,2026,2027')
    parser.add_argument('--drone-counts', default=None, help='Comma-separated drone counts')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    if args.batch_mode:
        seeds = [int(item) for item in (args.seeds or str(args.seed)).split(',')]
        drone_counts = [int(item) for item in (args.drone_counts or str(args.n_drones)).split(',')]
        results = run_sweep(
            protocol=args.protocol,
            seeds=seeds,
            drone_counts=drone_counts,
            output_dir=args.output_dir,
            experiment_name=args.experiment_name or f'{args.protocol.lower()}_batch',
            speeds=[args.speed] if args.speed is not None else [None],
            enable_poi=args.enable_poi,
            poi_counts=[args.poi_count] if args.poi_count is not None else [None],
            poi_speeds=[args.poi_speed] if args.poi_speed is not None else [None],
            weight_profile=args.weight_profile,
            predictor_mode=args.predictor_mode,
            cluster_algorithm=args.cluster_algorithm,
            traffic_rate=args.traffic_rate,
            comm_range=args.comm_range,
            sim_time_s=args.sim_time_s,
        )
        print({'runs': len(results), 'output_dir': args.output_dir})
    else:
        summary = run_once(
            args.protocol,
            args.seed,
            args.n_drones,
            args.output_dir,
            args.visualization,
            speed=args.speed,
            enable_poi=args.enable_poi,
            poi_count=args.poi_count,
            poi_speed=args.poi_speed,
            experiment_name=args.experiment_name,
            weight_profile=args.weight_profile,
            predictor_mode=args.predictor_mode,
            cluster_algorithm=args.cluster_algorithm,
            traffic_rate=args.traffic_rate,
            comm_range=args.comm_range,
            sim_time_s=args.sim_time_s,
        )
        print(summary)


if __name__ == '__main__':
    main()
