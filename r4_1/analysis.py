"""Deterministic offline R4-0 diagnostics from R3 snapshots."""
import argparse
import csv
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import linear_sum_assignment

OVERLAP_J = 0.25
OVERLAP_N = 2


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a or b else 1.0


def match_clusters(old, new):
    """Maximum total Jaccard, then threshold; IDs only index the output."""
    a, b = sorted(old), sorted(new)
    if not a or not b:
        return [], [], []
    scores = [[jaccard(old[x], new[y]) for y in b] for x in a]
    ii, jj = linear_sum_assignment([[-v for v in row] for row in scores])
    pairs = [(a[i], b[j], scores[i][j]) for i, j in zip(ii, jj)
             if scores[i][j] >= OVERLAP_J and len(old[a[i]] & new[b[j]]) >= OVERLAP_N]
    edges = [(x, y, jaccard(old[x], new[y])) for x in a for y in b
             if len(old[x] & new[y]) >= OVERLAP_N and jaccard(old[x], new[y]) >= OVERLAP_J]
    split = [x for x in a if sum(u == x for u, _, _ in edges) >= 2]
    merge = [y for y in b if sum(v == y for _, v, _ in edges) >= 2]
    return pairs, split, merge


def lifetimes(segments, horizon_us):
    """Segments: (identity, start_us, end_us|None, left_unknown)."""
    return [dict(identity=i, start_us=s, end_us=e if e is not None else horizon_us,
                 duration_s=((e if e is not None else horizon_us) - s) / 1e6,
                 left_boundary_unknown=left, right_censored=e is None)
            for i, s, e, left in segments]


def load_and_check(source):
    manifest = json.loads((source / "run_manifest.json").read_text())
    assert isinstance(manifest["seed"], int) and manifest["N_UAV"] in (60, 80, 100)
    assert manifest["simulation_duration_s"] == 300.0
    assert manifest["record_error_count"] == 0
    clusters = read_csv(source / "cluster_snapshots.csv")
    nodes = read_csv(source / "node_roles.csv")
    backbones = [json.loads(line) for line in (source / "backbone_snapshots.jsonl").read_text().splitlines()]
    assert len(backbones) == manifest["snapshot_count"] == 299
    by_t, nodes_t = defaultdict(dict), defaultdict(dict)
    for row in clusters:
        t, cid = int(float(row["time_us"])), int(row["cluster_id"])
        assert cid not in by_t[t]
        members = set(json.loads(row["member_ids"]))
        assert len(members) == int(row["member_count"]) and int(row["ch_id"]) in members
        by_t[t][cid] = dict(members=members, ch=int(row["ch_id"]))
    for row in nodes:
        t, nid = int(float(row["time_us"])), int(row["node_id"])
        assert nid not in nodes_t[t]
        nodes_t[t][nid] = row
    times = [int(float(b["time_us"])) for b in backbones]
    assert times == sorted(set(times)) == list(range(1_000_000, 300_000_000, 1_000_000))
    assert [b["epoch"] for b in backbones] == list(range(1, 300))
    for t, b in zip(times, backbones):
        assert t in by_t and t in nodes_t and len(nodes_t[t]) == manifest["N_UAV"] - 1
        groups = by_t[t]
        assert groups and set(map(int, b["cluster_membership"])) == set(groups)
        assert set(b["cluster_heads"]) == {v["ch"] for v in groups.values()}
        for cid, group in groups.items():
            assert group["members"] == set(b["cluster_membership"][str(cid)])
            for nid in group["members"]:
                role = nodes_t[t][nid]
                assert int(role["cluster_id"]) == cid and int(role["ch_id"]) == group["ch"]
        assert set().union(*(x["members"] for x in groups.values())) == set(nodes_t[t])
        assert {nid for nid, x in nodes_t[t].items() if x["is_backbone_connector"] == "True"} == set(b["backbone_relays"])
        for ch, path in b["paths_to_bs"].items():
            assert int(ch) in b["cluster_heads"] and isinstance(path, list) and path[0] == int(ch)
            assert len(path) == len(set(path)) and all(isinstance(n, int) and 0 <= n < manifest["N_UAV"] for n in path)
            if path[-1] == 0:
                assert all(n in set(b["cluster_heads"]) | set(b["backbone_relays"]) | {0} for n in path)
        assert isinstance(b["routes"], dict)
    return manifest, times, by_t, nodes_t, backbones, dict(
        snapshot_count=len(times), cluster_rows=len(clusters), node_rows=len(nodes),
        first_time_us=times[0], last_time_us=times[-1], missing_snapshots=0,
        malformed_rows=0, logged_errors=0, path_structures_valid=True)


def analyze(source, output):
    output.mkdir(parents=True, exist_ok=False)
    m, times, groups, roles, bb, integrity = load_and_check(source)
    (output / "integrity.json").write_text(json.dumps(integrity, indent=2) + "\n")
    size_rows, size_freq, trans, matches, backbone, ch_segments, stays = [], Counter(), [], [], [], [], []
    ch_open, stay_open = {}, {}
    identity, next_identity = {}, 1
    ch_switches = 0
    node_moves = Counter()
    event_by_t = defaultdict(Counter)
    path_changes_by_t = Counter()
    for k, t in enumerate(times):
        cur = groups[t]
        sizes = [len(v["members"]) for v in cur.values()]
        size_freq.update(sizes)
        size_rows.append(dict(time_us=t, time_s=t/1e6, epoch=k+1, cluster_count=len(cur),
                              mean_size=st.mean(sizes), median_size=st.median(sizes),
                              p10_size=quantile(sizes,.1), p90_size=quantile(sizes,.9), max_size=max(sizes)))
        b = bb[k]
        reachable = sum(path[-1] == 0 for path in b["paths_to_bs"].values())
        backbone.append(dict(time_us=t, time_s=t/1e6, epoch=k+1, br_count=len(b["backbone_relays"]),
                             reachable_ch=reachable, ch_count=len(cur), reachable_ch_ratio=reachable/len(cur),
                             br_toggles=0, path_changes=0, path_retention=None))
        if k == 0:
            for cid, v in sorted(cur.items()):
                identity[cid] = next_identity; next_identity += 1
                ch_open[identity[cid]] = (v["ch"], t, True)
            for nid, r in roles[t].items():
                stay_open[nid] = (identity[int(r["cluster_id"])], t, True)
            continue
        prev_t = times[k-1]; prev = groups[prev_t]
        old = {cid:v["members"] for cid,v in prev.items()}
        new = {cid:v["members"] for cid,v in cur.items()}
        pairs, splits, merges = match_clusters(old,new)
        matched_old={x for x,_,_ in pairs}; matched_new={y for _,y,_ in pairs}
        new_identity={y:identity[x] for x,y,_ in pairs}
        for y in sorted(set(cur)-matched_new):
            new_identity[y]=next_identity; next_identity+=1
        for x in sorted(set(prev)-matched_old):
            ch, start, left=ch_open.pop(identity[x])
            ch_segments.append((f"{identity[x]}:{ch}",start,t,left))
        for x,y,j in pairs:
            ident=identity[x]
            if prev[x]["ch"]!=cur[y]["ch"]:
                ch,start,left=ch_open.pop(ident)
                ch_segments.append((f"{ident}:{ch}",start,t,left))
                ch_open[ident]=(cur[y]["ch"],t,False)
                ch_switches+=1
        for y in sorted(set(cur)-matched_new):
            ch_open[new_identity[y]]=(cur[y]["ch"],t,False)
        old_node={nid:identity[int(r["cluster_id"])] for nid,r in roles[prev_t].items()}
        new_node={nid:new_identity[int(r["cluster_id"])] for nid,r in roles[t].items()}
        retained=sum(old_node[n]==new_node[n] for n in old_node.keys() & new_node.keys())
        for nid in sorted(new_node):
            if nid not in old_node or old_node[nid]!=new_node[nid]:
                if nid in stay_open:
                    ident,start,left=stay_open.pop(nid)
                    stays.append((f"{nid}:{ident}",start,t,left))
                    node_moves[nid]+=1
                stay_open[nid]=(new_node[nid],t,False)
        for nid in sorted(set(old_node)-set(new_node)):
            ident,start,left=stay_open.pop(nid)
            stays.append((f"{nid}:{ident}",start,t,left))
        entered=sum(len(new[y]-old[x]) for x,y,_ in pairs)
        exited=sum(len(old[x]-new[y]) for x,y,_ in pairs)
        for x,y,j in pairs:
            matches.append(dict(time_us=t, previous_cluster_id=x, cluster_id=y,
                                previous_identity=identity[x], identity=new_identity[y],
                                jaccard=j, overlap=len(old[x]&new[y]), event="continuation"))
        for x in sorted(set(prev)-matched_old):
            matches.append(dict(time_us=t,previous_cluster_id=x,cluster_id="",previous_identity=identity[x],identity="",jaccard="",overlap="",event="disappearance"))
        for y in sorted(set(cur)-matched_new):
            matches.append(dict(time_us=t,previous_cluster_id="",cluster_id=y,previous_identity="",identity=new_identity[y],jaccard="",overlap="",event="birth"))
        for x in splits:
            matches.append(dict(time_us=t,previous_cluster_id=x,cluster_id="",previous_identity=identity[x],identity="",jaccard="",overlap="",event="split"))
        for y in merges:
            matches.append(dict(time_us=t,previous_cluster_id="",cluster_id=y,previous_identity="",identity=new_identity[y],jaccard="",overlap="",event="merge"))
        event_by_t[t].update(split=len(splits),merge=len(merges))
        trans.append(dict(time_us=t,time_s=t/1e6,epoch=k+1,matched_clusters=len(pairs),
                          cluster_retention=len(pairs)/len(prev), ch_retention=sum(prev[x]["ch"]==cur[y]["ch"] for x,y,_ in pairs)/len(pairs) if pairs else None,
                          member_retention=retained/len(old_node), member_joins=entered,member_exits=exited,
                          member_change_rate=(entered+exited)/sum(len(v) for v in old.values()),
                          mean_jaccard=st.mean(j for _,_,j in pairs) if pairs else None,
                          split_count=len(splits),merge_count=len(merges)))
        old_br=set(bb[k-1]["backbone_relays"]); new_br=set(b["backbone_relays"])
        old_paths=bb[k-1]["paths_to_bs"];new_paths=b["paths_to_bs"]
        common=set(old_paths)&set(new_paths)
        changed=sum(old_paths[ch]!=new_paths[ch] for ch in common)
        path_changes_by_t[t]=changed
        backbone[-1].update(br_toggles=len(old_br^new_br),path_changes=changed,
                            path_retention=(len(common)-changed)/len(common) if common else None)
        identity=new_identity
    for ident,(ch,start,left) in ch_open.items():ch_segments.append((f"{ident}:{ch}",start,None,left))
    for nid,(ident,start,left) in stay_open.items():stays.append((f"{nid}:{ident}",start,None,left))
    horizon=int(m["simulation_duration_us"])
    ch_life=lifetimes(ch_segments,horizon); residence=lifetimes(stays,horizon)
    windows=[]
    for length in (1,2,3,5,10):
        for start in range(times[0],times[-1]-length*1_000_000+1,length*1_000_000):
            end=start+length*1_000_000
            old={cid:v["members"] for cid,v in groups[start].items()}
            new={cid:v["members"] for cid,v in groups[end].items()}
            pairs,_,_=match_clusters(old,new)
            t_events=[t for t in times if start<t<=end]
            windows.append(dict(window_s=length,start_us=start,end_us=end,
                member_retention=st.mean(j for _,_,j in pairs) if pairs else None,
                ch_retention=sum(groups[start][x]["ch"]==groups[end][y]["ch"] for x,y,_ in pairs)/len(pairs) if pairs else None,
                mean_abs_cluster_size_change=st.mean(abs(len(old[x])-len(new[y])) for x,y,_ in pairs) if pairs else None,
                split_count=sum(event_by_t[t]["split"] for t in t_events),
                merge_count=sum(event_by_t[t]["merge"] for t in t_events),
                path_changes=sum(path_changes_by_t[t] for t in t_events)))
    write_csv(output/'cluster_sizes.csv',size_rows,list(size_rows[0]))
    write_csv(output/'cluster_size_frequency.csv',[dict(size=k,frequency=v) for k,v in sorted(size_freq.items())],['size','frequency'])
    write_csv(output/'ch_lifetimes.csv',ch_life,list(ch_life[0]))
    write_csv(output/'member_stability.csv',trans,list(trans[0]))
    write_csv(output/'member_residence.csv',residence,list(residence[0]))
    write_csv(output/'cluster_events.csv',matches,list(matches[0]))
    write_csv(output/'backbone_stability.csv',backbone,list(backbone[0]))
    write_csv(output/'candidate_windows.csv',windows,list(windows[0]))
    summary=dict(integrity=integrity,mean_cluster_size=st.mean(v['mean_size'] for v in size_rows),
                 pooled_p90=quantile(list(size_freq.elements()),.9),ch_switches=ch_switches,
                 ch_tenure_median_s=st.median(x['duration_s'] for x in ch_life),
                 ch_complete_count=sum(not x['left_boundary_unknown'] and not x['right_censored'] for x in ch_life),
                 ch_right_censored=sum(x['right_censored'] for x in ch_life),
                 mean_member_retention=st.mean(x['member_retention'] for x in trans),
                 member_moves=sum(node_moves.values()),splits=sum(x['split_count'] for x in trans),
                 merges=sum(x['merge_count'] for x in trans),
                 windows={str(L):dict(count=sum(x['window_s']==L for x in windows),
                     member_retention=st.mean(x['member_retention'] for x in windows if x['window_s']==L and x['member_retention'] is not None),
                     ch_retention=st.mean(x['ch_retention'] for x in windows if x['window_s']==L and x['ch_retention'] is not None),
                     size_change=st.mean(x['mean_abs_cluster_size_change'] for x in windows if x['window_s']==L and x['mean_abs_cluster_size_change'] is not None),
                     splits=sum(x['split_count'] for x in windows if x['window_s']==L),
                     merges=sum(x['merge_count'] for x in windows if x['window_s']==L),
                     path_changes=sum(x['path_changes'] for x in windows if x['window_s']==L)) for L in (1,2,3,5,10)})
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    plot(output,size_freq,size_rows,ch_life,trans,summary,m)
    return summary


def quantile(values,q):
    x=sorted(values); i=(len(x)-1)*q; lo=int(i);hi=min(lo+1,len(x)-1)
    return x[lo]+(x[hi]-x[lo])*(i-lo)


def plot(out,freq,size_rows,ch_life,trans,summary,manifest):
    title=f"N={manifest['N_UAV']}, seed{manifest['seed']}, 300 s; sizes include CH"
    def save(name,x,y,xlabel,ylabel,kind='line'):
        fig,ax=plt.subplots(figsize=(7,4))
        if kind=='bar':ax.bar(x,y)
        elif kind=='hist':ax.hist(x,bins=25)
        else:ax.plot(x,y)
        ax.set(xlabel=xlabel,ylabel=ylabel,title=title);fig.tight_layout()
        fig.savefig(out/name,dpi=180);plt.close(fig)
    save('cluster_size_distribution.png',list(freq),list(freq.values()),'Members per cluster','Frequency','bar')
    save('cluster_count_timeseries.png',[x['time_s'] for x in size_rows],[x['cluster_count'] for x in size_rows],'Time (s)','Clusters')
    save('ch_tenure_distribution.png',[x['duration_s'] for x in ch_life if not x['left_boundary_unknown'] and not x['right_censored']],None,'Completed CH tenure (s)','Count','hist')
    save('member_retention_timeseries.png',[x['time_s'] for x in trans],[x['member_retention'] for x in trans],'Time (s)','Member retention')
    fig,ax=plt.subplots(figsize=(7,4));L=[1,2,3,5,10]
    ax.bar([v-.18 for v in L],[summary['windows'][str(v)]['member_retention'] for v in L],width=.36,label='Member Jaccard')
    ax.bar([v+.18 for v in L],[summary['windows'][str(v)]['ch_retention'] for v in L],width=.36,label='CH retention')
    ax.set(xlabel='Window length (s)',ylabel='Retention',title=title);ax.set_xticks(L);ax.legend();fig.tight_layout()
    fig.savefig(out/'candidate_window_stability.png',dpi=180);plt.close(fig)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('source',type=Path);ap.add_argument('output',type=Path)
    args=ap.parse_args();print(json.dumps(analyze(args.source,args.output),indent=2))
