import csv
import os
from collections import defaultdict

import numpy as np
from openpyxl import Workbook

from utils import config
from utils.util_function import euclidean_distance_3d


class Metrics:
    """
    Network-level statistics and export helpers for baseline and clustering studies.
    """

    def __init__(self, simulator):
        self.simulator = simulator

        self.control_packet_num = 0

        self.datapacket_generated = set()
        self.datapacket_arrived = set()
        self.datapacket_generated_num = 0
        self.delivered_bits = 0

        self.delivery_time = []
        self.deliver_time_dict = defaultdict()

        self.throughput = []
        self.throughput_dict = defaultdict()

        self.hop_cnt = []
        self.hop_cnt_dict = defaultdict()

        self.mac_delay = []

        self.collision_num = 0
        self.poi_coverage_ratio = []
        self.connected_ratio = []
        self.control_packet_breakdown = {
            'total': 0,
            'dsdv': 0,
            'backbone': 0,
            'cluster': 0,
        }
        self.routing_resilience = defaultdict(int)
        self.network_lifetime_us = None
        self.metric_timeseries = []

    def calculate_metrics(self, received_packet):
        latency = self.simulator.env.now - received_packet.creation_time
        self.deliver_time_dict[received_packet.packet_id] = latency
        self.throughput_dict[received_packet.packet_id] = received_packet.packet_length / (latency / 1e6)
        self.hop_cnt_dict[received_packet.packet_id] = received_packet.get_current_ttl()
        self.datapacket_arrived.add(received_packet.packet_id)
        self.delivered_bits += received_packet.packet_length

    def print_metrics(self):
        pdr = self._current_pdr()
        e2e_delay = self._current_e2e_delay()
        throughput = self._current_throughput()
        hop_cnt = self._current_hop_count()
        rl = self._current_routing_load()
        average_mac_delay = np.mean(self.mac_delay) if self.mac_delay else 0.0

        print('Totally send: ', self.datapacket_generated_num, ' data packets')
        print('Packet delivery ratio is: ', pdr, '%')
        print('Average end-to-end delay is: ', e2e_delay, 'ms')
        print('Routing load is: ', rl)
        print('Average throughput is: ', throughput, 'Kbps')
        print('Average hop count is: ', hop_cnt)
        print('Collision num is: ', self.collision_num)
        print('Average mac delay is: ', average_mac_delay, 'ms')

    def _current_pdr(self):
        if self.datapacket_generated_num == 0:
            return 0.0
        return len(self.datapacket_arrived) / self.datapacket_generated_num * 100

    def _current_e2e_delay(self):
        return np.mean(list(self.deliver_time_dict.values())) / 1e3 if self.deliver_time_dict else 0.0

    def _current_throughput(self):
        elapsed_seconds = max(self.simulator.env.now / 1e6, 1e-9)
        return (self.delivered_bits / elapsed_seconds) / 1e3

    def _current_hop_count(self):
        return np.mean(list(self.hop_cnt_dict.values())) if self.hop_cnt_dict else 0.0

    def _current_routing_load(self):
        return self.control_packet_num / len(self.datapacket_arrived) if self.datapacket_arrived else 0.0

    def _current_connectivity_ratio(self):
        drones = [drone for drone in self.simulator.drones if not getattr(drone, 'is_base_station', False)]
        node_count = len(drones)
        if node_count == 0:
            return 0.0

        adjacency = {drone.identifier: set() for drone in drones}
        for idx, drone in enumerate(drones):
            for other in drones[idx + 1:]:
                if euclidean_distance_3d(drone.coords, other.coords) <= config.COMMUNICATION_RANGE:
                    adjacency[drone.identifier].add(other.identifier)
                    adjacency[other.identifier].add(drone.identifier)

        visited = set()
        largest_component = 0
        for drone in drones:
            if drone.identifier in visited:
                continue
            stack = [drone.identifier]
            size = 0
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                size += 1
                stack.extend(adjacency[current] - visited)
            largest_component = max(largest_component, size)
        return largest_component / node_count

    def record_timeseries(self):
        self.metric_timeseries.append({
            'time_s': self.simulator.env.now / 1e6,
            'pdr_percent': self._current_pdr(),
            'e2e_delay_ms': self._current_e2e_delay(),
            'throughput_kbps': self._current_throughput(),
            'routing_load': self._current_routing_load(),
            'connectivity_ratio': self._current_connectivity_ratio(),
            'control_packet_total': self.control_packet_breakdown['total'],
            'control_packet_dsdv': self.control_packet_breakdown['dsdv'],
            'control_packet_backbone': self.control_packet_breakdown['backbone'],
            'control_packet_cluster': self.control_packet_breakdown['cluster'],
        })

    def collect_summary(self):
        pdr = self._current_pdr()
        e2e_delay = self._current_e2e_delay()
        throughput = self._current_throughput()
        hop_cnt = self._current_hop_count()
        rl = self._current_routing_load()
        average_mac_delay = np.mean(self.mac_delay) if self.mac_delay else 0.0
        residual_energy = sum(drone.residual_energy for drone in self.simulator.drones)
        initial_energy = config.INITIAL_ENERGY * len(self.simulator.drones)
        energy_consumption = max(0.0, initial_energy - residual_energy)
        if self.network_lifetime_us is None:
            sleeping = [drone for drone in self.simulator.drones if getattr(drone, 'sleep', False)]
            if sleeping:
                self.network_lifetime_us = self.simulator.env.now
        network_lifetime = (self.network_lifetime_us or self.simulator.env.now) / 1e6
        poi_coverage = np.mean(self.poi_coverage_ratio) if self.poi_coverage_ratio else 0.0
        connected_ratio = np.mean(self.connected_ratio) if self.connected_ratio else self._current_connectivity_ratio()
        cluster_summary = {}
        if getattr(self.simulator, 'cluster_manager', None) is not None:
            cluster_summary = self.simulator.cluster_manager.metrics.summary()

        summary = {
            'experiment': config.EXPERIMENT_NAME,
            'protocol': config.ROUTING_PROTOCOL,
            'seed': self.simulator.seed,
            'number_of_drones': self.simulator.n_drones,
            'pdr_percent': pdr,
            'e2e_delay_ms': e2e_delay,
            'routing_load': rl,
            'throughput_kbps': throughput,
            'hop_count': hop_cnt,
            'collision_num': self.collision_num,
            'mac_delay_ms': average_mac_delay,
            'datapacket_generated': self.datapacket_generated_num,
            'datapacket_arrived': len(self.datapacket_arrived),
            'control_packet_num': self.control_packet_num,
            'control_packet_total': self.control_packet_breakdown['total'],
            'control_packet_dsdv': self.control_packet_breakdown['dsdv'],
            'control_packet_backbone': self.control_packet_breakdown['backbone'],
            'control_packet_cluster': self.control_packet_breakdown['cluster'],
            'residual_energy_j': residual_energy,
            'energy_consumption_j': energy_consumption,
            'network_lifetime_s': network_lifetime,
            'poi_coverage_ratio': poi_coverage,
            'connected_ratio': connected_ratio,
            'mobility_model': config.MOBILITY_MODEL,
            'comm_range_m': config.COMMUNICATION_RANGE,
        }
        summary.update(self._routing_resilience_summary())
        summary.update(cluster_summary)
        return summary

    def export_results(self, output_dir=None):
        output_root = output_dir or config.RESULTS_DIR
        metrics_dir = os.path.join(output_root, config.RESULTS_METRICS_DIRNAME)
        figures_dir = os.path.join(output_root, config.RESULTS_FIGURES_DIRNAME)
        os.makedirs(metrics_dir, exist_ok=True)
        os.makedirs(figures_dir, exist_ok=True)
        summary = self.collect_summary()

        csv_path = os.path.join(metrics_dir, f'{config.EXPERIMENT_NAME}_summary.csv')
        xlsx_path = os.path.join(metrics_dir, f'{config.EXPERIMENT_NAME}_summary.xlsx')

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
            writer.writeheader()
            writer.writerow(summary)

        wb = Workbook()
        ws = wb.active
        ws.title = 'summary'
        ws.append(list(summary.keys()))
        ws.append(list(summary.values()))
        wb.save(xlsx_path)

        self._export_timeseries(metrics_dir)
        self._export_control_breakdown(metrics_dir)
        if getattr(self.simulator, 'cluster_manager', None) is not None:
            self.simulator.cluster_manager.metrics.export(metrics_dir)
        self._export_figures(figures_dir)

        return csv_path, xlsx_path, summary

    def _export_timeseries(self, metrics_dir):
        self._write_rows(os.path.join(metrics_dir, 'connectivity_ratio_timeseries.csv'), [
            {'time_s': row['time_s'], 'connectivity_ratio': row['connectivity_ratio']}
            for row in self.metric_timeseries
        ])
        self._write_rows(os.path.join(metrics_dir, 'throughput_timeseries.csv'), [
            {'time_s': row['time_s'], 'throughput_kbps': row['throughput_kbps']}
            for row in self.metric_timeseries
        ])
        self._write_rows(os.path.join(metrics_dir, 'pdr_timeseries.csv'), [
            {'time_s': row['time_s'], 'pdr_percent': row['pdr_percent']}
            for row in self.metric_timeseries
        ])
        self._write_rows(os.path.join(metrics_dir, 'control_overhead_timeseries.csv'), self.metric_timeseries)

    def _export_control_breakdown(self, metrics_dir):
        control_row = {
            'control_packet_total': self.control_packet_breakdown['total'],
            'control_packet_dsdv': self.control_packet_breakdown['dsdv'],
            'control_packet_backbone': self.control_packet_breakdown['backbone'],
            'control_packet_cluster': self.control_packet_breakdown['cluster'],
            'routing_load': self._current_routing_load(),
            'unit_control_overhead': self.control_packet_breakdown['total'] / max(1, len(self.datapacket_arrived)),
        }
        control_row.update(self._routing_resilience_summary())
        self._write_rows(os.path.join(metrics_dir, 'control_overhead_breakdown.csv'), [control_row])
        self._write_rows(os.path.join(metrics_dir, 'routing_fallback_breakdown.csv'), [self._routing_resilience_summary()])

    def _export_figures(self, figures_dir):
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            return

        def plot_line(rows, x_key, y_key, filename, ylabel):
            if not rows:
                return
            plt.figure()
            plt.plot([row[x_key] for row in rows], [row[y_key] for row in rows])
            plt.xlabel('Time (s)')
            plt.ylabel(ylabel)
            plt.tight_layout()
            plt.savefig(os.path.join(figures_dir, filename))
            plt.close()

        plot_line(self.metric_timeseries, 'time_s', 'connectivity_ratio', 'connectivity_ratio_curve.png', 'Connectivity Ratio')
        plot_line(self.metric_timeseries, 'time_s', 'throughput_kbps', 'throughput_curve.png', 'Throughput (kbps)')
        plot_line(self.metric_timeseries, 'time_s', 'pdr_percent', 'pdr_curve.png', 'PDR (%)')
        if getattr(self.simulator, 'cluster_manager', None) is not None:
            samples = self.simulator.cluster_manager.metrics.cluster_lifetime_samples
            if samples:
                plt.figure()
                plt.plot(list(range(1, len(samples) + 1)), samples)
                plt.xlabel('Cluster Sample')
                plt.ylabel('Cluster Lifetime (rounds)')
                plt.tight_layout()
                plt.savefig(os.path.join(figures_dir, 'cluster_lifetime_curve.png'))
                plt.close()

        try:
            plt.figure()
            labels = ['DSDV', 'Backbone', 'Cluster']
            values = [
                self.control_packet_breakdown['dsdv'],
                self.control_packet_breakdown['backbone'],
                self.control_packet_breakdown['cluster'],
            ]
            plt.bar(labels, values)
            plt.ylabel('Control Packets')
            plt.tight_layout()
            plt.savefig(os.path.join(figures_dir, 'control_overhead_breakdown.png'))
            plt.close()
        except Exception:
            plt.close('all')

        self._plot_uav_trajectories(figures_dir)
        self._plot_cluster_snapshot(figures_dir)

    def _plot_uav_trajectories(self, figures_dir):
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            return

        if not any(getattr(drone, 'trajectory_trace', None) for drone in self.simulator.drones):
            return

        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        for drone in self.simulator.drones:
            trace = getattr(drone, 'trajectory_trace', [])
            if not trace:
                continue
            x = [step['coords'][0] for step in trace]
            y = [step['coords'][1] for step in trace]
            z = [step['coords'][2] for step in trace]
            ax.plot(x, y, z, linewidth=0.8, alpha=0.8)
        ax.set_xlim(0, config.MAP_LENGTH)
        ax.set_ylim(0, config.MAP_WIDTH)
        ax.set_zlim(0, config.MAP_HEIGHT)
        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')
        ax.set_zlabel('Z (m)')
        fig.tight_layout()
        fig.savefig(os.path.join(figures_dir, 'uav_3d_trajectory.png'))
        plt.close(fig)

    def _plot_cluster_snapshot(self, figures_dir):
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            return

        drones = [drone for drone in self.simulator.drones if not getattr(drone, 'is_base_station', False)]
        if not drones:
            return

        plt.figure()
        for drone in drones:
            color = 'tab:red' if getattr(drone, 'cluster_role', None) == 'CH' else 'tab:blue'
            plt.scatter(drone.coords[0], drone.coords[1], c=color, s=45 if color == 'tab:red' else 20)
            cluster_head = getattr(drone, 'cluster_head', None)
            if cluster_head is not None and cluster_head.identifier != drone.identifier:
                plt.plot([drone.coords[0], cluster_head.coords[0]], [drone.coords[1], cluster_head.coords[1]], color='lightgray', linewidth=0.5)
        plt.xlim(0, config.MAP_LENGTH)
        plt.ylim(0, config.MAP_WIDTH)
        plt.xlabel('X (m)')
        plt.ylabel('Y (m)')
        plt.tight_layout()
        plt.savefig(os.path.join(figures_dir, 'cluster_structure_snapshot.png'))
        plt.close()

    def update_poi_metrics(self, simulator):
        if not getattr(simulator, 'pois', None):
            return

        coverage_hits = 0
        connected_hits = 0
        for poi in simulator.pois:
            covered = False
            connected = False
            for drone in simulator.drones:
                if euclidean_distance_3d(poi.coords, drone.coords) <= config.COMMUNICATION_RANGE:
                    covered = True
                    if getattr(drone, 'cluster_role', None) in ('CH', 'BS'):
                        connected = True
                        break
            if covered:
                coverage_hits += 1
            if connected:
                connected_hits += 1

        total = len(simulator.pois)
        self.poi_coverage_ratio.append(coverage_hits / total if total else 0.0)
        self.connected_ratio.append(connected_hits / total if total else 0.0)

    def increment_control_packets(self, count=1, category='total'):
        self.control_packet_num += count
        self.control_packet_breakdown['total'] += count
        if category in self.control_packet_breakdown:
            self.control_packet_breakdown[category] += count

    def record_routing_event(self, event_name, count=1):
        self.routing_resilience[event_name] += count

    def _routing_resilience_summary(self):
        keys = [
            'cm_local_backup_count',
            'backbone_local_backup_count',
            'fallback_attempt_count',
            'fallback_success_count',
            'fallback_fail_already_used_count',
            'fallback_fail_missing_target_count',
            'fallback_fail_no_candidate_count',
            'fallback_extra_control_packets',
        ]
        return {key: self.routing_resilience.get(key, 0) for key in keys}

    def _write_rows(self, path, rows):
        rows = rows or []
        fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else ['placeholder']
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            if rows:
                writer.writerows(rows)
