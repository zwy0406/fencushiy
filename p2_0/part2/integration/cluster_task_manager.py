"""Deterministic task groups over read-only Part1 network states.

This is a pure integration layer. It neither schedules events nor moves UAVs.
Defaults are engineering starting points, not experimentally selected values.
"""
from dataclasses import dataclass, field
from math import isfinite
from typing import Optional, Tuple


@dataclass(frozen=True)
class TaskGroupView:
    task_group_id: str
    task_group_members: Tuple[int, ...]
    service_uav_ids: Tuple[int, ...]
    task_group_anchor: Tuple[float, float, float]
    group_creation_time_us: int
    last_update_time_us: int
    group_status: str
    network_cluster_id: Optional[int]
    network_ch_id: Optional[int]


@dataclass
class _Group:
    group_id: str
    members: set
    service_ids: Tuple[int, ...]
    anchor: Tuple[float, float, float]
    created_us: int
    updated_us: int
    cluster_id: Optional[int]
    ch_id: Optional[int]
    status: str = 'active'
    pending_members: Optional[frozenset] = None
    pending_count: int = 0
    missing_count: int = 0
    route_loss_count: int = 0


@dataclass(frozen=True)
class TaskGroupPolicy:
    match_jaccard: float = 0.40
    change_confirmations: int = 2
    missing_confirmations: int = 2
    route_loss_confirmations: int = 2
    min_hold_us: int = 2_000_000
    min_energy_ratio: float = 0.25
    critical_relay_energy_ratio: float = 0.50

    def __post_init__(self):
        if not 0 < self.match_jaccard <= 1:
            raise ValueError('match_jaccard must be in (0,1]')
        if min(self.change_confirmations, self.missing_confirmations,
               self.route_loss_confirmations) < 1 or self.min_hold_us < 0:
            raise ValueError('invalid confirmation or hold duration')
        if not 0 <= self.min_energy_ratio <= self.critical_relay_energy_ratio <= 1:
            raise ValueError('invalid energy ratios')


def _jaccard(a, b):
    return len(a & b) / len(a | b) if a or b else 1.0


def _centroid(members, nodes):
    points = [nodes[n].position_m for n in sorted(members)]
    return tuple(sum(p[i] for p in points) / len(points) for i in range(3))


def _critical_relays(state):
    # Internal path hops bear backbone load; CH and BR are not categorically banned.
    return {nid for path in state.paths_to_bs.values() for nid in path[1:-1]}


def _network_ch(state, members):
    heads = sorted(nid for nid in members if nid in state.nodes
                   and state.nodes[nid].cluster_role == 'CH')
    return heads[0] if heads else None


def select_service_uavs(state, members, coverage_candidates, busy_ids=(),
                        current_service_ids=(), policy=None):
    """Select only explicitly nominated PoI candidates that meet network limits.

    A coverage planner supplies `coverage_candidates`; if absent, selection is
    empty. Existing service nodes may remain busy with their own current task.
    """
    policy = policy or TaskGroupPolicy()
    candidates = set(coverage_candidates or ())
    busy = set(busy_ids) - set(current_service_ids)
    critical = _critical_relays(state)
    selected = []
    for nid in sorted(set(members) & candidates):
        node = state.nodes.get(nid)
        if node is None or nid in busy or not node.available or not node.route_available_now:
            continue
        ratio = node.residual_energy_j / node.initial_energy_j if node.initial_energy_j > 0 else 0
        floor = (policy.critical_relay_energy_ratio if nid in critical
                 else policy.min_energy_ratio)
        if ratio >= floor:
            selected.append(nid)
    return tuple(selected)


class ClusterTaskManager:
    def __init__(self, policy=None):
        self.policy = policy or TaskGroupPolicy()
        self._groups = {}
        self._next_id = 1
        self._last_time_us = -1

    def _new_group(self, members, cluster_id, state):
        gid = f'tg-{self._next_id:06d}'
        self._next_id += 1
        group = _Group(gid, set(members), (), _centroid(members, state.nodes),
                       state.time_us, state.time_us, cluster_id,
                       _network_ch(state, members))
        self._groups[gid] = group
        return group

    def advance(self, state, coverage_candidates=None, busy_ids=()):
        """Consume one published snapshot; change only this manager's state."""
        if state.time_us <= self._last_time_us:
            raise ValueError('network snapshots must have increasing time_us')
        self._last_time_us = state.time_us
        candidates = {
            int(cid): frozenset(nid for nid in members
                                if nid in state.nodes and state.nodes[nid].available)
            for cid, members in state.clusters.items()
        }
        candidates = {cid: members for cid, members in candidates.items() if members}
        scores = []
        for gid, group in self._groups.items():
            for cid, members in candidates.items():
                similarity = _jaccard(group.members, members)
                if similarity >= self.policy.match_jaccard and group.members & members:
                    scores.append((-similarity, gid, cid))
        matched_groups, matched_clusters = set(), set()
        matches = []
        for _, gid, cid in sorted(scores):
            if gid not in matched_groups and cid not in matched_clusters:
                matched_groups.add(gid); matched_clusters.add(cid)
                matches.append((gid, cid))
        for gid in sorted(set(self._groups) - matched_groups):
            group = self._groups[gid]
            group.missing_count += 1
            group.status = 'degraded'
            if (group.missing_count >= self.policy.missing_confirmations
                    and state.time_us - group.created_us >= self.policy.min_hold_us):
                del self._groups[gid]
        for gid, cid in matches:
            group = self._groups[gid]
            desired = candidates[cid]
            group.cluster_id = cid
            group.ch_id = _network_ch(state, desired)
            group.missing_count = 0
            # Unavailable UAVs are removed immediately; ordinary network churn
            # must survive confirmation and hold time.
            unavailable = {nid for nid in group.members
                           if nid not in state.nodes or not state.nodes[nid].available}
            if unavailable:
                group.members -= unavailable
                group.updated_us = state.time_us
            if frozenset(group.members) == desired:
                group.pending_members = None; group.pending_count = 0
            else:
                if group.pending_members == desired:
                    group.pending_count += 1
                else:
                    group.pending_members = desired; group.pending_count = 1
                if (group.pending_count >= self.policy.change_confirmations
                        and state.time_us - group.updated_us >= self.policy.min_hold_us):
                    claimed_elsewhere = set().union(
                        *(other.members for other_id, other in self._groups.items()
                          if other_id != gid))
                    revised = set(desired) - claimed_elsewhere
                    if revised:
                        group.members = revised
                        group.anchor = _centroid(revised, state.nodes)
                        group.updated_us = state.time_us
                    group.pending_members = None; group.pending_count = 0
            group.route_loss_count = (group.route_loss_count + 1 if not any(
                state.nodes[n].route_available_now for n in group.members if n in state.nodes)
                else 0)
            group.status = ('degraded' if group.route_loss_count >=
                            self.policy.route_loss_confirmations else 'active')
        claimed = set().union(*(g.members for g in self._groups.values())) if self._groups else set()
        for cid, members in sorted(candidates.items()):
            if cid not in matched_clusters:
                new_members = set(members) - claimed
                if new_members:
                    self._new_group(new_members, cid, state)
                    claimed.update(new_members)
        for group in self._groups.values():
            group.service_ids = select_service_uavs(
                state, group.members, coverage_candidates, busy_ids,
                group.service_ids, self.policy)
        owner_ids = [n for group in self._groups.values() for n in group.members]
        if len(owner_ids) != len(set(owner_ids)):
            raise AssertionError('a UAV cannot belong to two task groups')
        return self.snapshot()

    def snapshot(self):
        return tuple(TaskGroupView(
            task_group_id=g.group_id, task_group_members=tuple(sorted(g.members)),
            service_uav_ids=g.service_ids, task_group_anchor=g.anchor,
            group_creation_time_us=g.created_us, last_update_time_us=g.updated_us,
            group_status=g.status, network_cluster_id=g.cluster_id,
            network_ch_id=g.ch_id,
        ) for g in sorted(self._groups.values(), key=lambda x: x.group_id))


def max_legal_displacement(d_max_m, v_max_m_s, decision_period_s):
    """P2-0 bound only; does not change drone coordinates or schedule movement."""
    values = (float(d_max_m), float(v_max_m_s), float(decision_period_s))
    if any(not isfinite(x) or x <= 0 for x in values):
        raise ValueError('movement limits and period must be positive and finite')
    return min(values[0], values[1] * values[2])


def bounded_move(requested_distance_m, d_max_m, v_max_m_s, decision_period_s):
    requested = float(requested_distance_m)
    if not isfinite(requested) or requested < 0:
        raise ValueError('requested distance must be nonnegative and finite')
    return min(requested, max_legal_displacement(d_max_m, v_max_m_s,
                                                 decision_period_s))
