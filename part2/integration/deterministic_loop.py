"""Opt-in P2-1B assembly. Simulator and the caller own the two clocks."""

from dataclasses import dataclass
from math import dist, isfinite

from entities.drone import Drone
from simulator.simulator import Simulator
from utils import config

from .cluster_task_manager import ClusterTaskManager
from .movement_controller import MovementController
from .network_state_adapter import NetworkStateAdapter


class _ControlledDrone(Drone):
    def _build_mobility_model(self):
        limits = self.simulator.controlled_limits.get(self.identifier)
        if limits is None:
            return super()._build_mobility_model()
        return MovementController(self, limits, (config.MAP_LENGTH, config.MAP_WIDTH))


class DeterministicSimulator(Simulator):
    drone_class = _ControlledDrone

    def __init__(self, seed, env, channel_states, n_drones, *, controlled_limits,
                 total_simulation_time=None):
        self.controlled_limits = dict(controlled_limits)
        if not self.controlled_limits.keys() <= set(range(n_drones)) - {config.BS_NODE_ID}:
            raise ValueError("controlled IDs must name UAVs, excluding the BS")
        if (not config.USE_BASE_STATION or config.ROUTING_PROTOCOL != "MWMP_DCA"
                or config.TRACE_ONLY or config.MOBILITY_TRACE_MODE != "live"):
            raise ValueError("P2-1B requires live MWMP_DCA with a BS")
        super().__init__(seed, env, channel_states, n_drones, total_simulation_time)


@dataclass(frozen=True)
class Coverage:
    total_pois: int
    geometric_ids: frozenset
    effective_ids: frozenset


class DeterministicLoop:
    """Issue explicit PoI assignments and sample coverage from current state."""

    def __init__(self, simulator, sensing_radius_m):
        if not isfinite(sensing_radius_m) or sensing_radius_m <= 0:
            raise ValueError("sensing radius must be finite and positive")
        self.adapter = NetworkStateAdapter(simulator)
        self.manager = ClusterTaskManager()
        self.controllers = {d.identifier: d.mobility_model for d in simulator.drones
                            if isinstance(d.mobility_model, MovementController)}
        self.radius = sensing_radius_m
        self.assignments = {}

    def decide(self, assignments, actions, duration_us):
        """Assignments map UAV ID to PoI IDs. Actions are (heading_rad, metres)."""
        assignments = {nid: frozenset(poi_ids) for nid, poi_ids in assignments.items()}
        if not actions.keys() <= assignments.keys() <= self.controllers.keys():
            raise ValueError("actions require an assignment and a controlled UAV")
        for nid, controller in self.controllers.items():
            controller.validate_action(*actions.get(nid, (0.0, 0.0)), duration_us)
        state = self.adapter.capture()
        groups = self.manager.advance(state, coverage_candidates=assignments)
        service = {nid for group in groups if group.group_status == "active"
                   for nid in group.service_uav_ids}
        self.assignments = {nid: pois for nid, pois in assignments.items() if nid in service}
        for nid, controller in self.controllers.items():
            action = actions.get(nid, (0.0, 0.0)) if nid in service else (0.0, 0.0)
            controller.set_action(*action, duration_us)
        return groups

    def evaluate(self, pois):
        """Pois map IDs to 3D coordinates in metres. Route proxy, not packet delivery."""
        state = self.adapter.capture()
        geometric, effective = set(), set()
        for nid, ids in self.assignments.items():
            node = state.nodes.get(nid)
            if node is None or not node.available:
                continue
            for pid in ids & pois.keys():
                if dist(node.position_m, pois[pid]) <= self.radius:
                    geometric.add(pid)
                    if node.route_available_now:
                        effective.add(pid)
        return Coverage(len(pois), frozenset(geometric), frozenset(effective))
