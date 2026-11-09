"""Offline association diagnostics; never mutates the three R4-1 runs."""
import argparse
import csv
import json
import statistics as stats
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'r4_1_a3_seed2025_20261106'))
from analysis import match_clusters, jaccard  # noqa: E402


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8') as f:
        out = csv.DictWriter(f, fieldnames=fields)
        out.writeheader()
        out.writerows(rows)


def mean(values):
    values = [x for x in values if x is not None]
    return stats.mean(values) if values else None


def cohort(rows):
    total = len(rows)
    counts = Counter(r['outcome'] for r in rows)
    delivered = counts['delivered']
    pending = counts['IncompleteAtHorizon']
    delays = [float(r['e2e_delay_us']) / 1e3 for r in rows if r['outcome'] == 'delivered']
    return dict(total=total, delivered=delivered, incomplete=pending,
                pdr_lower=delivered / total if total else None,
                pdr_upper=(delivered + pending) / total if total else None,
                resolved_pdr=delivered / (total - pending) if total > pending else None,
                delivered_delay_ms=mean(delays),
                drops=total - delivered - pending,
                route_failure=counts['RouteUnavailable'] + counts['MigrationExhausted'],
                packet_lifetime=counts['PacketLifetime'], max_retry=counts['MaxRetry'])


def load_run(root, n):
    run = root / f'n{n}'
    name = f'r4_1_proposed_n{n}_seed2025'
    snap = run / 'cluster_snapshot_logs' / name
    manifest = json.loads((snap / 'run_manifest.json').read_text())
    assert manifest['seed'] == 2025 and manifest['N_UAV'] == n
    assert manifest['simulation_duration_s'] == 300.0
    assert manifest['record_error_count'] == 0
    cluster = defaultdict(dict)
    for r in read_csv(snap / 'cluster_snapshots.csv'):
        t = int(float(r['time_us']))
        cluster[t][int(r['cluster_id'])] = (int(r['ch_id']), set(json.loads(r['member_ids'])))
    backbone = {int(float(b['time_us'])): b for b in (json.loads(x) for x in (snap / 'backbone_snapshots.jsonl').read_text().splitlines())}
    assert len(cluster) == len(backbone) == 299
    node_roles = read_csv(snap / 'node_roles.csv')
    assert len(node_roles) == (n - 1) * len(cluster)
    roles_by_t = defaultdict(dict)
    for r in node_roles:
        t = int(float(r['time_us'])); nid = int(r['node_id'])
        assert nid not in roles_by_t[t]
        roles_by_t[t][nid] = r
    for t, groups in cluster.items():
        assert len(roles_by_t[t]) == n - 1
        for cid, (ch, members) in groups.items():
            assert ch in members
            for nid in members:
                r = roles_by_t[t][nid]
                assert int(r['cluster_id']) == cid and int(r['ch_id']) == ch
                assert (r['is_backbone_connector'] == 'True') == (nid in backbone[t]['backbone_relays'])
    outcomes = read_csv(run / 'metrics' / 'packet_outcomes.csv')
    by_sec = defaultdict(list)
    for r in outcomes:
        creation = int(float(r['creation_time']))
        assert 0 <= creation < 300_000_000
        by_sec[creation // 1_000_000].append(r)
    summary = next(iter(read_csv(next((run / 'metrics').glob('*_summary.csv')))))
    assert int(float(summary['datapacket_generated'])) == len(outcomes)
    return manifest, cluster, backbone, node_roles, outcomes, by_sec, summary


def group_stats(clusters):
    return {cid: members for cid, (_, members) in clusters.items()}


def path_available(b, ch):
    path = b['paths_to_bs'].get(str(ch))
    return bool(path and path[0] == ch and path[-1] == 0)


def analyze(root, out):
    assert not out.exists(), out
    out.mkdir(parents=True)
    event_rows, assoc_rows, path_rows, interval_rows = [], [], [], []
    audits = []
    for n in (60, 80, 100):
        manifest, cluster, bb, node_roles, outcomes, by_sec, summary = load_run(root, n)
        times = sorted(cluster)
        assert times == list(range(1_000_000, 300_000_000, 1_000_000))
        events = []
        for i in range(1, len(times)):
            t, prev = times[i], times[i-1]
            older, newer = cluster[prev], cluster[t]
            pairs, splits, merges = match_clusters(group_stats(older), group_stats(newer))
            matched_prev = {x for x, _, _ in pairs}
            matched_next = {y for _, y, _ in pairs}
            rotations = [(x, y, j) for x, y, j in pairs if older[x][0] != newer[y][0]]
            path_common = set(bb[prev]['paths_to_bs']) & set(bb[t]['paths_to_bs'])
            path_changes = sum(bb[prev]['paths_to_bs'][ch] != bb[t]['paths_to_bs'][ch] for ch in path_common)
            old_br, new_br = set(bb[prev]['backbone_relays']), set(bb[t]['backbone_relays'])
            old_avail = sum(path_available(bb[prev], ch) for ch in bb[prev]['cluster_heads']) / len(bb[prev]['cluster_heads'])
            new_avail = sum(path_available(bb[t], ch) for ch in bb[t]['cluster_heads']) / len(bb[t]['cluster_heads'])
            path_rows.append(dict(N=n, seed=2025, time_us=t, time_s=t/1e6,
                                  ch_rotations=len(rotations), member_changes=sum(older[x][1] != newer[y][1] for x,y,_ in pairs),
                                  br_toggles=len(old_br ^ new_br), path_changes_common_ch=path_changes,
                                  common_ch_count=len(path_common), snapshot_path_available_before=old_avail,
                                  snapshot_path_available_after=new_avail,
                                  split_events=len(splits), merge_events=len(merges)))
            for x,y,j in rotations:
                events.append(dict(N=n, seed=2025, time_us=t, time_s=t/1e6,
                                   previous_cluster_id=x, cluster_id=y, old_ch=older[x][0], new_ch=newer[y][0],
                                   jaccard=j, old_size=len(older[x][1]), new_size=len(newer[y][1]),
                                   members_changed=older[x][1] != newer[y][1], br_toggles=len(old_br ^ new_br),
                                   paths_changed=path_changes, path_available_before=path_available(bb[prev], older[x][0]),
                                   path_available_after=path_available(bb[t], newer[y][0])))
        event_rows.extend(events)
        event_times = sorted({e['time_us'] for e in events})
        for w in (1,2,3,5):
            eligible = [e for e in events if e['time_s'] >= w and e['time_s'] + w <= 300]
            # Strict isolation requires no other network rotation inside either window.
            strict = [e for e in eligible if not any(abs(e['time_us'] - t) <= w*1_000_000 and t != e['time_us'] for t in event_times)
                      and sum(x['time_us'] == e['time_us'] for x in events) == 1]
            # A disjoint sensitivity subset prevents packet cohort reuse; other events can still contaminate it.
            disjoint, last_end = [], -1
            for e in sorted(eligible, key=lambda x:(x['time_us'],x['previous_cluster_id'])):
                if e['time_us'] - w*1_000_000 >= last_end:
                    disjoint.append(e)
                    last_end = e['time_us'] + w*1_000_000
            for label, sample in [('all',eligible),('strict_isolated',strict),('disjoint_sample',disjoint)]:
                before, after = [], []
                for e in sample:
                    sec=int(e['time_s'])
                    a=[r for s in range(sec-w,sec) for r in by_sec[s]]
                    b=[r for s in range(sec,sec+w) for r in by_sec[s]]
                    before.append(cohort(a)); after.append(cohort(b))
                def change(key):
                    return mean(y[key]-x[key] for x,y in zip(before,after) if x[key] is not None and y[key] is not None)
                assoc_rows.append(dict(N=n,seed=2025,window_s=w,selection=label,event_count=len(sample),
                    generated_before=sum(x['total'] for x in before),generated_after=sum(x['total'] for x in after),
                    incomplete_before=sum(x['incomplete'] for x in before),incomplete_after=sum(x['incomplete'] for x in after),
                    mean_pdr_lower_before=mean(x['pdr_lower'] for x in before),mean_pdr_lower_after=mean(x['pdr_lower'] for x in after),
                    mean_pdr_lower_delta=change('pdr_lower'),mean_pdr_upper_delta=change('pdr_upper'),
                    mean_resolved_pdr_delta=change('resolved_pdr'),
                    mean_delivered_delay_delta_ms=change('delivered_delay_ms'),
                    mean_drop_delta=change('drops'),mean_route_failure_delta=change('route_failure'),
                    mean_packet_lifetime_delta=change('packet_lifetime'),
                    mean_path_available_delta=mean(e['path_available_after']-e['path_available_before'] for e in sample),
                    simultaneous_member_change=sum(e['members_changed'] for e in sample),
                    simultaneous_br_change=sum(e['br_toggles']>0 for e in sample),
                    simultaneous_path_change=sum(e['paths_changed']>0 for e in sample)))
        # Endpoint structure and communication cohort rates within complete windows.
        for w in (1,2,3,5,10):
            window_rows=[]
            for start_s in range(1,300-w,w):
                end_s=start_s+w
                a,b=cluster[start_s*1_000_000],cluster[end_s*1_000_000]
                pairs,_,_=match_clusters(group_stats(a),group_stats(b))
                cohort_rows=[r for sec in range(start_s,end_s) for r in by_sec[sec]]
                c=cohort(cohort_rows)
                old_b,new_b=bb[start_s*1_000_000],bb[end_s*1_000_000]
                common=set(old_b['paths_to_bs']) & set(new_b['paths_to_bs'])
                window_rows.append(dict(member_jaccard=mean(j for _,_,j in pairs),
                    ch_retention=mean(float(a[x][0]==b[y][0]) for x,y,_ in pairs),
                    size_change=mean(abs(len(a[x][1])-len(b[y][1])) for x,y,_ in pairs),
                    path_retention=mean(float(old_b['paths_to_bs'][ch]==new_b['paths_to_bs'][ch]) for ch in common),
                    path_available=mean(float(path_available(new_b,ch)) for ch in new_b['cluster_heads']),
                    pdr_lower=c['pdr_lower'],pdr_upper=c['pdr_upper'],incomplete=c['incomplete'],
                    delivered_delay_ms=c['delivered_delay_ms']))
            interval_rows.append(dict(N=n,seed=2025,window_s=w,complete_windows=len(window_rows),
                **{key:mean(r[key] for r in window_rows) for key in ('member_jaccard','ch_retention','size_change','path_retention','path_available','pdr_lower','pdr_upper','delivered_delay_ms')},
                incomplete_packets=sum(r['incomplete'] for r in window_rows)))
        with (root/f'n{n}'/'metrics'/'packet_hops.csv').open(newline='', encoding='utf-8') as f:
            hop_fields = csv.DictReader(f).fieldnames
        audits.append(dict(N=n,snapshots=len(times),packet_rows=len(outcomes),
            packet_outcomes=Counter(r['outcome'] for r in outcomes),
            metrics_fields=list(summary), hop_fields=hop_fields,
            snapshot_count_manifest=manifest['snapshot_count']))
    write_csv(out/'ch_rotation_communication.csv',assoc_rows,list(assoc_rows[0]))
    write_csv(out/'ch_rotation_events.csv',event_rows,list(event_rows[0]))
    write_csv(out/'backbone_path_stability.csv',path_rows,list(path_rows[0]))
    write_csv(out/'decision_interval_diagnostics.csv',interval_rows,list(interval_rows[0]))
    (out/'data_audit.json').write_text(json.dumps(audits,indent=2,default=dict)+'\n')
    return audits


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();print(json.dumps(analyze(a.source,a.output),default=dict)[:1000])
