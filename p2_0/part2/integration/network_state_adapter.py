"""Copy a published Part1 network state into detached, immutable primitives.

`route_available_now` is a conservative path/geometry proxy, not packet PDR.
This module never calls the planner or changes SimPy time.
"""
from dataclasses import dataclass
from math import dist, isfinite
from types import MappingProxyType
from typing import Mapping, Optional, Tuple


@dataclass(frozen=True)
class NodeState:
    node_id: int
    position_m: Tuple[float, float, float]
    residual_energy_j: float
    initial_energy_j: float
    available: bool
    cluster_id: Optional[int]
    ch_id: Optional[int]
    cluster_role: str
    is_backbone_relay: bool
    planned_path_to_bs: Tuple[int, ...]
    planned_path_available: bool
    route_available_now: bool


@dataclass(frozen=True)
class NetworkState:
    time_us: int
    snapshot_time_us: int
    epoch: int
    bs_id: int
    nodes: Mapping[int, NodeState]
    clusters: Mapping[int, Tuple[int, ...]]
    cluster_heads: Tuple[int, ...]
    backbone_relays: Tuple[int, ...]
    paths_to_bs: Mapping[int, Tuple[int, ...]]
    routes: Mapping[int, Mapping[int, int]]
    communication_range_m: float


def _node_id(node):
    if node is None:
        return None
    return int(node.identifier if hasattr(node, 'identifier') else node)


def _walk_route(source, bs_id, routes, limit):
    path, seen = [source], {source}
    while path[-1] != bs_id and len(path) <= limit:
        next_id = routes.get(path[-1], {}).get(bs_id)
        if next_id is None or next_id in seen:
            return ()
        path.append(next_id)
        seen.add(next_id)
    return tuple(path) if path[-1] == bs_id else ()


class NetworkStateAdapter:
    """Read only already-published `active_snapshot` plus current Drone fields."""

    def __init__(self, simulator, communication_range_m=None, bs_id=None):
        self.simulator = simulator
        if communication_range_m is None or bs_id is None:
            from utils import config
            communication_range_m = (config.COMMUNICATION_RANGE if communication_range_m is None
                                     else communication_range_m)
            bs_id = config.BS_NODE_ID if bs_id is None else bs_id
        self.communication_range_m = float(communication_range_m)
        self.bs_id = int(bs_id)
        if not isfinite(self.communication_range_m) or self.communication_range_m <= 0:
            raise ValueError('communication range must be positive and finite')

    def capture(self):
        manager = getattr(self.simulator, 'cluster_manager', None)
        planner = getattr(manager, 'backbone_planner', None)
        snapshot = getattr(planner, 'active_snapshot', None)
        if snapshot is None or int(snapshot.epoch) <= 0:
            raise RuntimeError('Part1 has not published a backbone snapshot')
        drones = tuple(self.simulator.drones)
        by_id = {int(d.identifier): d for d in drones}
        if len(by_id) != len(drones) or self.bs_id not in by_id:
            raise ValueError('duplicate node ID or missing BS')
        positions = {nid: tuple(float(x) for x in d.coords) for nid, d in by_id.items()}
        if any(len(p) != 3 or not all(isfinite(x) for x in p) for p in positions.values()):
            raise ValueError('all positions must be finite 3D coordinates')
        active = {nid for nid, d in by_id.items()
                  if not getattr(d, 'sleep', False)
                  and float(getattr(d, 'residual_energy', 0.0)) > 0}
        edges = frozenset((int(a), int(b)) for a, b in snapshot.valid_edges)
        paths = {int(k): tuple(int(x) for x in v) for k, v in snapshot.paths_to_bs.items()}
        routes = {int(a): {int(b): int(hop) for b, hop in row.items()}
                  for a, row in snapshot.routes.items()}
        clusters = {int(k): tuple(sorted(int(x) for x in v))
                    for k, v in snapshot.cluster_membership.items()}
        heads = tuple(sorted(int(x) for x in snapshot.cluster_heads))
        relays = tuple(sorted(int(x) for x in snapshot.backbone_relays))
        nodes = {}
        for nid, drone in sorted(by_id.items()):
            if getattr(drone, 'is_base_station', False):
                continue
            ch_id = _node_id(getattr(drone, 'cluster_head', None))
            path = paths.get(nid, ()) if nid in heads else _walk_route(nid, self.bs_id, routes, len(by_id))
            # The planner's route table covers backbone nodes; a CM may need a
            # one-hop attachment to its CH before following the CH path.
            if not path and ch_id is not None and ch_id != nid:
                ch_path = paths.get(ch_id, ())
                if ch_path and (nid, ch_id) in edges:
                    path = (nid,) + ch_path
            planned = bool(path and path[0] == nid and path[-1] == self.bs_id)
            valid_now = planned and all(
                a in active and b in active and (a, b) in edges
                and dist(positions[a], positions[b]) <= self.communication_range_m
                for a, b in zip(path, path[1:])
            )
            nodes[nid] = NodeState(
                node_id=nid, position_m=positions[nid],
                residual_energy_j=float(drone.residual_energy),
                initial_energy_j=float(drone.initial_energy),
                available=nid in active and float(drone.residual_energy) > 0,
                cluster_id=(None if getattr(drone, 'cluster_id', None) is None
                            else int(drone.cluster_id)),
                ch_id=ch_id, cluster_role=str(drone.cluster_role),
                is_backbone_relay=nid in relays,
                planned_path_to_bs=path,
                planned_path_available=planned,
                route_available_now=bool(valid_now),
            )
        return NetworkState(
            time_us=int(self.simulator.env.now),
            snapshot_time_us=int(snapshot.created_time_us), epoch=int(snapshot.epoch),
            bs_id=self.bs_id, nodes=MappingProxyType(nodes),
            clusters=MappingProxyType(clusters), cluster_heads=heads,
            backbone_relays=relays, paths_to_bs=MappingProxyType(paths),
            routes=MappingProxyType({k: MappingProxyType(v) for k, v in routes.items()}),
            communication_range_m=self.communication_range_m,
        )
