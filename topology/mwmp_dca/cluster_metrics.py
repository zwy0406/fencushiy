import csv
import os
from collections import defaultdict


class ClusterMetrics:
    def __init__(self):
        self.cluster_lifetimes = []
        self.cluster_head_lifetimes = []
        self.reclustering_events = 0
        self.cluster_sizes = []
        self.average_tlet = []
        self.cluster_lifetime_samples = []
        self.ch_lifetime_samples = []
        self.backoff_times = []
        self.predictor_rmse = []
        self.predictor_mae = []
        self.weight_factor_samples = defaultdict(list)
        self.topology_scores = []
        self.backbone_connectivity_ratios = []
        self.bs_reachability_ratios = []
        self.backbone_path_preservation_ratios = []
        self.bs_reachability_efficiencies = []
        self.ch_announce_count = 0
        self.join_request_count = 0
        self.suppressed_election_count = 0
        self.cluster_head_changes = defaultdict(int)
        self.cluster_head_churn_fractions = []
        self.previous_heads = set()
        self.previous_snapshot = {}
        self.head_start_round = {}
        self.snapshot_start_round = {}
        self.election_rounds = []
        self.round_timeseries = []
        self.current_round = 0

    def record_cluster_snapshot(self, clusters, round_counter=0):
        self.current_round = max(self.current_round, round_counter)
        self.cluster_sizes.append([len(members) for _, members in clusters])
        current_heads = {head_id for head_id, _ in clusters}
        if self.previous_heads:
            changed = len(current_heads.symmetric_difference(self.previous_heads))
            self.cluster_head_churn_fractions.append(
                changed / max(1, len(current_heads | self.previous_heads))
            )
            if changed:
                self.cluster_head_lifetimes.append(changed)
            for old_head in self.previous_heads - current_heads:
                start = self.head_start_round.pop(old_head, round_counter)
                self.ch_lifetime_samples.append(max(0, round_counter - start))
        for head_id in current_heads:
            self.head_start_round.setdefault(head_id, round_counter)
        self.previous_heads = current_heads

        current_snapshot = {head_id: tuple(sorted(members)) for head_id, members in clusters}
        if self.previous_snapshot:
            for head_id, members in self.previous_snapshot.items():
                if current_snapshot.get(head_id) != members:
                    start = self.snapshot_start_round.pop(head_id, round_counter)
                    self.cluster_lifetime_samples.append(max(0, round_counter - start))
        for head_id in current_snapshot:
            self.snapshot_start_round.setdefault(head_id, round_counter)
        self.previous_snapshot = current_snapshot

        mean_size = 0.0
        if clusters:
            mean_size = sum(len(members) for _, members in clusters) / len(clusters)
        self.round_timeseries.append({
            'round': round_counter,
            'cluster_count': len(clusters),
            'cluster_head_count': len(current_heads),
            'mean_cluster_size': mean_size,
        })

    def record_reclustering(self):
        self.reclustering_events += 1

    def record_average_tlet(self, value):
        self.average_tlet.append(value)

    def record_backoff_time(self, value):
        self.backoff_times.append(value)

    def record_control_exchange(self, announces=0, joins=0, suppressed=0):
        self.ch_announce_count += announces
        self.join_request_count += joins
        self.suppressed_election_count += suppressed

    def record_prediction_error(self, error):
        if error is None:
            return
        rmse, mae = error
        self.predictor_rmse.append(rmse)
        self.predictor_mae.append(mae)

    def record_weight_factors(self, factors):
        for key, value in factors.items():
            self.weight_factor_samples[key].append(value)

    def record_topology_score(self, value):
        self.topology_scores.append(value)

    def record_backbone_connectivity(
        self,
        connectivity_ratio,
        bs_reachability_ratio,
        path_preservation_ratio=0.0,
        bs_reachability_efficiency=0.0,
    ):
        self.backbone_connectivity_ratios.append(connectivity_ratio)
        self.bs_reachability_ratios.append(bs_reachability_ratio)
        self.backbone_path_preservation_ratios.append(path_preservation_ratio)
        self.bs_reachability_efficiencies.append(bs_reachability_efficiency)

    def record_election_round(self, round_counter, candidate_ids, winner_ids, suppressed=0, formation_time_us=0.0, backoff_map=None):
        self.election_rounds.append({
            'round': round_counter,
            'candidate_count': len(candidate_ids),
            'winner_count': len(winner_ids),
            'candidate_ids': '|'.join(str(item) for item in candidate_ids),
            'winner_ids': '|'.join(str(item) for item in winner_ids),
            'suppressed_count': suppressed,
            'formation_time_ms': formation_time_us / 1e3,
            'mean_backoff_ms': (sum(backoff_map.values()) / len(backoff_map) / 1e3) if backoff_map else 0.0,
            'max_backoff_ms': (max(backoff_map.values()) / 1e3) if backoff_map else 0.0,
        })

    def _mean(self, values):
        return sum(values) / len(values) if values else 0.0

    def summary(self):
        mean_cluster_size = 0.0
        if self.cluster_sizes:
            flattened = [size for snapshot in self.cluster_sizes for size in snapshot]
            mean_cluster_size = sum(flattened) / len(flattened) if flattened else 0.0

        round_count = len(self.round_timeseries)
        mean_tlet = self._mean(self.average_tlet)
        backbone_partition_rounds = sum(
            1 for value in self.backbone_connectivity_ratios if value < 1.0 - 1e-9
        )
        cluster_head_change_count = sum(self.cluster_head_lifetimes) if self.cluster_head_lifetimes else 0
        active_ch_lifetimes = [
            max(0, self.current_round - start) for start in self.head_start_round.values()
        ]
        active_cluster_lifetimes = [
            max(0, self.current_round - start) for start in self.snapshot_start_round.values()
        ]
        summary = {
            'reclustering_rate': self.reclustering_events,
            'cluster_head_change_count': cluster_head_change_count,
            'cluster_head_change_rate': cluster_head_change_count / max(1, round_count),
            'cluster_head_churn_ratio': self._mean(self.cluster_head_churn_fractions),
            'mean_cluster_size': mean_cluster_size,
            'average_tlet': mean_tlet,
            'cluster_lifetime': self._mean(self.cluster_lifetime_samples),
            'ch_lifetime': self._mean(self.ch_lifetime_samples),
            'mean_cluster_tenure_rounds': self._mean(
                self.cluster_lifetime_samples + active_cluster_lifetimes
            ),
            'mean_ch_tenure_rounds': self._mean(
                self.ch_lifetime_samples + active_ch_lifetimes
            ),
            'mean_backoff_time_us': self._mean(self.backoff_times),
            'clustering_delay_ms': self._mean([row['formation_time_ms'] for row in self.election_rounds]),
            'ch_announce_count': self.ch_announce_count,
            'join_request_count': self.join_request_count,
            'suppressed_election_count': self.suppressed_election_count,
            'predictor_rmse': self._mean(self.predictor_rmse),
            'predictor_mae': self._mean(self.predictor_mae),
            'mean_topology_score': self._mean(self.topology_scores),
            'mean_backbone_connectivity_ratio': self._mean(self.backbone_connectivity_ratios),
            'mean_bs_reachability_ratio': self._mean(self.bs_reachability_ratios),
            'mean_backbone_path_preservation_ratio': self._mean(
                self.backbone_path_preservation_ratios
            ),
            'mean_bs_reachability_efficiency': self._mean(
                self.bs_reachability_efficiencies
            ),
            'backbone_partition_rounds': backbone_partition_rounds,
            'backbone_partition_ratio': (
                backbone_partition_rounds / len(self.backbone_connectivity_ratios)
                if self.backbone_connectivity_ratios else 0.0
            ),
        }
        for key, values in self.weight_factor_samples.items():
            summary[f'mean_{key}'] = self._mean(values)
        return summary

    def export(self, output_dir):
        os.makedirs(output_dir, exist_ok=True)
        self._write_rows(
            os.path.join(output_dir, 'cluster_lifetime.csv'),
            [{'sample_index': idx, 'cluster_lifetime_rounds': value} for idx, value in enumerate(self.cluster_lifetime_samples, start=1)],
        )
        self._write_rows(
            os.path.join(output_dir, 'prediction_error_rmse_mae.csv'),
            [
                {'sample_index': idx, 'rmse': rmse, 'mae': mae}
                for idx, (rmse, mae) in enumerate(zip(self.predictor_rmse, self.predictor_mae), start=1)
            ],
        )
        self._write_rows(os.path.join(output_dir, 'election_trace.csv'), self.election_rounds)
        self._write_rows(os.path.join(output_dir, 'cluster_round_timeseries.csv'), self.round_timeseries)

    def _write_rows(self, path, rows):
        rows = rows or []
        fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else ['placeholder']
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            if rows:
                writer.writerows(rows)
