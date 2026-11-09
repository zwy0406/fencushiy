"""P2-0 offline fixtures: no simulator process or learning model is started."""
import json
import unittest
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

from part2.integration.network_state_adapter import NetworkStateAdapter, NetworkState, NodeState
from part2.integration.cluster_task_manager import (
    ClusterTaskManager, TaskGroupPolicy, bounded_move, max_legal_displacement,
    select_service_uavs,
)


def state(time_us=1_000_000, clusters=None, br=(), unreachable=(), energy=None):
    clusters = clusters or {1: (1, 2, 3, 4)}
    energy = energy or {}
    ids = sorted(set().union(*map(set, clusters.values())))
    heads = set(clusters)
    nodes = {}
    for cid, members in clusters.items():
        for nid in members:
            nodes[nid] = NodeState(nid, (float(nid), 0., 0.),
                                   energy.get(nid, 100.), 100., True, cid, cid,
                                   'CH' if nid == cid else 'CM', nid in br,
                                   (nid, 0), True, nid not in unreachable)
    return NetworkState(time_us, time_us, time_us // 1_000_000, 0,
                        MappingProxyType(nodes), MappingProxyType(dict(clusters)),
                        tuple(sorted(heads)), tuple(br),
                        MappingProxyType({cid: (cid, 0) for cid in heads}),
                        MappingProxyType({}), 250.)


class AdapterTests(unittest.TestCase):
    def test_live_snapshot_is_detached_and_read_only(self):
        drones = [SimpleNamespace(identifier=0, coords=[0., 0., 0.],
                                  is_base_station=True, sleep=False,
                                  residual_energy=100.),
                  SimpleNamespace(identifier=1, coords=[10., 0., 0.],
                                  is_base_station=False, sleep=False,
                                  residual_energy=80., initial_energy=100.,
                                  cluster_id=1, cluster_role='CH', cluster_head=1),
                  SimpleNamespace(identifier=2, coords=[20., 0., 0.],
                                  is_base_station=False, sleep=False,
                                  residual_energy=70., initial_energy=100.,
                                  cluster_id=1, cluster_role='CM', cluster_head=1)]
        published = SimpleNamespace(
            epoch=1, created_time_us=1_000_000,
            valid_edges={(1, 0), (2, 1)}, cluster_heads={1},
            backbone_relays=set(), cluster_membership={1: (1, 2)},
            paths_to_bs={1: (1, 0)}, routes={1: {0: 0}})
        sim = SimpleNamespace(env=SimpleNamespace(now=1_000_000), drones=drones,
                              cluster_manager=SimpleNamespace(
                                  backbone_planner=SimpleNamespace(active_snapshot=published)))
        before = (sim.env.now, list(drones[2].coords), dict(published.paths_to_bs))
        captured = NetworkStateAdapter(sim, 250., 0).capture()
        self.assertEqual(captured.nodes[2].planned_path_to_bs, (2, 1, 0))
        self.assertTrue(captured.nodes[2].route_available_now)
        self.assertEqual(before, (sim.env.now, drones[2].coords, published.paths_to_bs))
        drones[2].coords[0] = 900.
        self.assertEqual(captured.nodes[2].position_m, (20., 0., 0.))
        moved = NetworkStateAdapter(sim, 250., 0).capture()
        self.assertTrue(moved.nodes[2].planned_path_available)
        self.assertFalse(moved.nodes[2].route_available_now)
        with self.assertRaises(TypeError):
            captured.nodes[1] = None

    def test_unpublished_snapshot_rejected(self):
        sim = SimpleNamespace(cluster_manager=SimpleNamespace(
            backbone_planner=SimpleNamespace(active_snapshot=SimpleNamespace(epoch=0))))
        with self.assertRaises(RuntimeError):
            NetworkStateAdapter(sim, 250., 0).capture()


class GroupTests(unittest.TestCase):
    def setUp(self):
        self.policy = TaskGroupPolicy(min_hold_us=0)

    def test_ch_and_cluster_id_change_preserve_task_id(self):
        manager = ClusterTaskManager(self.policy)
        first = manager.advance(state(clusters={1: (1, 2, 3)}))[0]
        second = manager.advance(state(2_000_000, {2: (1, 2, 3)}))[0]
        self.assertEqual(first.task_group_id, second.task_group_id)
        self.assertEqual(second.task_group_members, (1, 2, 3))
        self.assertEqual(second.network_ch_id, 2)

    def test_addition_needs_confirmation_unavailable_exit_is_immediate(self):
        manager = ClusterTaskManager(self.policy)
        manager.advance(state(clusters={1: (1, 2, 3)}))
        self.assertEqual(manager.advance(state(2_000_000, {1: (1, 2, 3, 4)}))[0]
                         .task_group_members, (1, 2, 3))
        self.assertEqual(manager.advance(state(3_000_000, {1: (1, 2, 3, 4)}))[0]
                         .task_group_members, (1, 2, 3, 4))
        s = state(4_000_000, {1: (1, 2, 3, 4)})
        nodes = dict(s.nodes); nodes[4] = replace(nodes[4], available=False)
        s = replace(s, nodes=MappingProxyType(nodes))
        self.assertEqual(manager.advance(s)[0].task_group_members, (1, 2, 3))

    def test_split_then_merge_never_duplicates_uav(self):
        manager = ClusterTaskManager(self.policy)
        first = manager.advance(state())[0].task_group_id
        for t in (2, 3):
            groups = manager.advance(state(t * 1_000_000, {1: (1, 2), 3: (3, 4)}))
        self.assertEqual(len(groups), 2)
        self.assertIn(first, [g.task_group_id for g in groups])
        self.assertEqual(sorted(n for g in groups for n in g.task_group_members), [1, 2, 3, 4])
        for t in (4, 5):
            groups = manager.advance(state(t * 1_000_000, {1: (1, 2, 3, 4)}))
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].task_group_id, first)
        self.assertEqual(groups[0].task_group_members, (1, 2, 3, 4))

    def test_br_change_and_short_path_loss_do_not_rebuild(self):
        manager = ClusterTaskManager(self.policy)
        first = manager.advance(state(), coverage_candidates={1, 2, 3})[0]
        second = manager.advance(state(2_000_000, br=(3,), unreachable=(1, 2, 3, 4)),
                                 coverage_candidates={1, 2, 3})[0]
        self.assertEqual(first.task_group_id, second.task_group_id)
        self.assertEqual(second.group_status, 'active')
        self.assertEqual(second.service_uav_ids, ())
        third = manager.advance(state(3_000_000, br=(3,), unreachable=(1, 2, 3, 4)))[0]
        self.assertEqual(third.group_status, 'degraded')
        recovered = manager.advance(state(4_000_000))[0]
        self.assertEqual(recovered.group_status, 'active')

    def test_explicit_service_candidates_energy_busy_and_relay_load(self):
        s = state(br=(3,), energy={1: 80., 2: 20., 3: 40., 4: 80.})
        s = replace(s, paths_to_bs=MappingProxyType({1: (1, 3, 0)}))
        self.assertEqual(select_service_uavs(s, {1, 2, 3, 4}, {1, 2, 3, 4},
                                              busy_ids={4}, policy=self.policy), (1,))
        self.assertEqual(select_service_uavs(s, {1, 2, 3, 4}, None,
                                              policy=self.policy), ())

    def test_time_monotonicity(self):
        manager = ClusterTaskManager(self.policy)
        s = state()
        manager.advance(s)
        with self.assertRaises(ValueError):
            manager.advance(s)


class MotionTests(unittest.TestCase):
    def test_candidate_period_limits(self):
        self.assertEqual([max_legal_displacement(50, 15, dt) for dt in (2, 3, 5)],
                         [30, 45, 50])
        self.assertEqual(bounded_move(100, 50, 15, 2), 30)
        with self.assertRaises(ValueError):
            bounded_move(-1, 50, 15, 2)


class HistoricalSnapshotTests(unittest.TestCase):
    def test_r4_snapshot_membership_offline(self):
        root = Path(__file__).resolve().parents[1]
        file = root / 'results/r4_1_a3_seed2025_20261106/n60/cluster_snapshot_logs/' \
                      'r4_1_proposed_n60_seed2025/backbone_snapshots.jsonl'
        if not file.exists():
            self.skipTest('R4-1 archive unavailable in this checkout')
        with file.open() as f:
            records = [json.loads(next(f)) for _ in range(2)]
        manager = ClusterTaskManager(self.policy())
        for b in records:
            memberships = {int(k): tuple(v) for k, v in b['cluster_membership'].items()}
            s = state(int(b['time_us']), memberships, tuple(b['backbone_relays']))
            groups = manager.advance(s)
            ids = [nid for group in groups for nid in group.task_group_members]
            self.assertEqual(len(ids), len(set(ids)))

    @staticmethod
    def policy():
        return TaskGroupPolicy(min_hold_us=0)


if __name__ == '__main__':
    unittest.main()
