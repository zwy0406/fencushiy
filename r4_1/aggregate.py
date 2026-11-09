"""Combine the three approved single-seed R4-1 diagnostics for reporting."""
import csv
import json
import re
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SIZES = (60, 80, 100)


def rows(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


def write(path, data):
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


summary, sizes, stability, windows = [], [], [], []
for n in SIZES:
    stage = json.loads((ROOT / f'n{n}_stage.json').read_text())
    assert stage['state'] == 'passed', stage
    base = ROOT / f'n{n}_analysis'
    metrics = json.loads((base / 'summary.json').read_text())
    validation = json.loads((ROOT / f'n{n}_validation.json').read_text())
    run_log = (ROOT / f'n{n}.log').read_text()
    wall_values = re.findall(r"'wall_clock_s': ([0-9.]+)", run_log)
    assert wall_values, f'wall clock absent for N={n}'
    wall_clock_s = float(wall_values[-1])
    frequency = rows(base / 'cluster_size_frequency.csv')
    size_rows = rows(base / 'cluster_sizes.csv')
    ch = rows(base / 'ch_lifetimes.csv')
    member = rows(base / 'member_residence.csv')
    adj = rows(base / 'member_stability.csv')
    bb = rows(base / 'backbone_stability.csv')
    complete_ch = [float(x['duration_s']) for x in ch if x['right_censored'] == 'False' and x['left_boundary_unknown'] == 'False']
    complete_member = [float(x['duration_s']) for x in member if x['right_censored'] == 'False' and x['left_boundary_unknown'] == 'False']
    total_clusters = sum(int(x['frequency']) for x in frequency)
    pooled_mean = sum(int(x['size']) * int(x['frequency']) for x in frequency) / total_clusters
    summary.append(dict(N=n, seed=2025, snapshots=validation['snapshot_count'], wall_clock_s=wall_clock_s,
                        packet_count=validation['packet_count'], energy_error_j=validation['energy_error_j'],
                        mean_cluster_count=st.mean(int(x['cluster_count']) for x in size_rows),
                        pooled_mean_cluster_size=pooled_mean, pooled_p90_cluster_size=metrics['pooled_p90'],
                        ch_complete_tenure_mean_s=st.mean(complete_ch),
                        ch_complete_tenure_median_s=st.median(complete_ch),
                        ch_complete_segments=len(complete_ch), ch_right_censored=metrics['ch_right_censored'],
                        member_complete_residence_mean_s=st.mean(complete_member),
                        member_complete_residence_median_s=st.median(complete_member),
                        adjacent_member_retention=metrics['mean_member_retention'],
                        split_events=metrics['splits'], merge_events=metrics['merges'],
                        mean_br_count=st.mean(int(x['br_count']) for x in bb),
                        br_toggles=sum(int(x['br_toggles']) for x in bb),
                        common_ch_path_changes=sum(int(x['path_changes']) for x in bb),
                        mean_bs_reachable_ch_ratio=st.mean(float(x['reachable_ch_ratio']) for x in bb)))
    for x in size_rows:
        sizes.append(dict(N=n, seed=2025, **x))
    for x in adj:
        stability.append(dict(N=n, seed=2025, **x))
    for L in (1, 2, 3, 5, 10):
        w = metrics['windows'][str(L)]
        windows.append(dict(N=n, seed=2025, window_s=L, complete_windows=w['count'],
                            member_retention=w['member_retention'], ch_retention=w['ch_retention'],
                            mean_abs_cluster_size_change=w['size_change'],
                            split_events=w['splits'], merge_events=w['merges'],
                            common_ch_path_changes=w['path_changes'],
                            path_changes_per_window=w['path_changes']/w['count']))
write(ROOT / 'r4_1_summary.csv', summary)
write(ROOT / 'r4_1_cluster_size.csv', sizes)
write(ROOT / 'r4_1_stability.csv', stability)
write(ROOT / 'r4_1_decision_windows.csv', windows)

lines = ['# R4-1 单种子规模诊断', '',
         'Proposed；N=60/80/100；seed2025；每组 300 s。三组是同一个种子下的不同规模，不构成多种子统计结论。', '',
         '| N | 墙钟 s | 簇数均值 | 簇规模均值/P90（含 CH） | 完整 CH 任职均值 s | 相邻成员保持率 | 分裂/合并 | BR 数均值 | 可达 BS 的 CH 比例 |',
         '| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
for r in summary:
    lines.append(f"| {r['N']} | {r['wall_clock_s']:.1f} | {r['mean_cluster_count']:.2f} | {r['pooled_mean_cluster_size']:.2f}/{r['pooled_p90_cluster_size']:.0f} | {r['ch_complete_tenure_mean_s']:.2f} | {r['adjacent_member_retention']:.3f} | {r['split_events']}/{r['merge_events']} | {r['mean_br_count']:.2f} | {r['mean_bs_reachable_ch_ratio']:.3f} |")
lines += ['', '## 计算口径', '',
          '簇规模包括 CH；簇延续由相邻快照的最大总 Jaccard 一对一匹配建立，且要求 J≥0.25、交集至少 2 架 UAV。分裂/合并另从完整重叠图识别。CH 与成员驻留持续时间使用 time_us；首轮任职起点未知，末轮仍在任视为右删失；表中 CH 均值仅用两端完整的任职段。',
          '相邻成员保持率为追踪簇身份后 UAV 原簇身份不变的比例。BR 翻转为相邻快照 BR 集合对称差计数。BS 可达率依据 paths_to_bs 以 BS 0 结尾。路径变化只比较相邻快照共有的 CH，新生/消失 CH 不计入。',
          '', '## 周期窗口', '',
          '窗口端点基于真实 time_us，自首个 1 s 快照起按完整长度取样；事件取 (start,end]。末尾不足完整窗口的时段丢弃。成员保持率为端点匹配簇平均 Jaccard；不能从此推出覆盖率或能耗最优。', '',
          '| N | 周期 s | 窗口数 | 成员保持率 | CH 保持率 | 平均规模变化 | 分裂/合并 | 路径变化/窗口 |',
          '| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
for r in windows:
    lines.append(f"| {r['N']} | {r['window_s']} | {r['complete_windows']} | {r['member_retention']:.3f} | {r['ch_retention']:.3f} | {r['mean_abs_cluster_size_change']:.2f} | {r['split_events']}/{r['merge_events']} | {r['path_changes_per_window']:.2f} |")
lines += ['', '## 数据与限制', '',
          '每个规模的原始指标、移动轨迹、R3 快照、manifest、验收 JSON、分析 CSV/PNG 均在独立 n60/n80/n100 目录。上述四份 r4_1_*.csv 可直接导入 Origin。',
          'ClusterMetrics 的 mean_cluster_size 为跨簇合并平均；其 CH 生命周期按全局 CH ID 和轮次计算，R4-1 使用跨快照匹配的簇身份及真实时间戳，并排除边界未知或右删失段，因此定义不同。',
          'service_uav_ids 尚无定义；Part2 应把任务群身份独立于易变的 CH/cluster_id，并为结构事件保留触发更新接口。', '']
(ROOT / 'r4_1_report.md').write_text('\n'.join(lines), encoding='utf-8')
