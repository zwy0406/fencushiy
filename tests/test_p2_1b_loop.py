import unittest
import random
from math import dist
from unittest.mock import patch

import simpy

from part2.integration.deterministic_loop import DeterministicLoop, DeterministicSimulator
from part2.integration.movement_controller import MovementController, MovementLimits
from part2.p2_1b_smoke import packet_counts
from mobility.gauss_markov_3d import GaussMarkov3D
from simulator.simulator import Simulator
from utils import config


class DeterministicLoopTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(random.setstate, random.getstate())
        options = dict(NUMBER_OF_DRONES=2, USE_BASE_STATION=True, BS_NODE_ID=0,
                       BS_POSITION=(500, 500, 150), ROUTING_PROTOCOL="MWMP_DCA",
                       ENABLE_VISUALIZATION=False, ENABLE_PLOTS=False,
                       ENABLE_POI=False, TRACE_ONLY=False, MOBILITY_TRACE_MODE="live",
                       HETEROGENEOUS=False, ENABLE_CLUSTER_SNAPSHOT_LOGGING=False)
        self.enterContext(patch.multiple(config, **options))
        self.enterContext(patch("simulator.simulator.start_coords.get_random_start_point_3d",
                                return_value=[(500, 500, 150), (730, 500, 150)]))

    def make_sim(self, controlled=None, count=2):
        env = simpy.Environment()
        channels = {i: simpy.Resource(env, capacity=1) for i in range(count)}
        kwargs = dict(seed=2025, env=env, channel_states=channels, n_drones=count,
                      total_simulation_time=20_000_000)
        if controlled is None:
            return Simulator(**kwargs)
        return DeterministicSimulator(**kwargs, controlled_limits=controlled)

    def test_real_movement_route_refresh_and_coverage(self):
        sim = self.make_sim({1: MovementLimits(100, 20)})
        loop = DeterministicLoop(sim, 50)
        drone = sim.drones[1]
        self.assertIsInstance(drone.mobility_model, MovementController)
        self.assertIsNone(sim.drones[0].mobility_model)
        # Run just after the first network epoch and movement tick.
        sim.env.run(until=1_000_001)
        # SimPy's numeric until advances now by one microsecond. Make the
        # decision at the next physical tick, after that tick has executed.
        start = sim.env.timeout(99_999)
        sim.env.run(until=start)
        before = loop.adapter.capture()
        self.assertTrue(before.nodes[1].route_available_now)
        self.assertEqual(loop.decide({1: {7}}, {1: (0.0, 100)}, 2_000_000)[0].service_uav_ids,
                         (1,))
        pois = {7: (750, 500, 150), 8: (750, 500, 150)}
        self.assertEqual(loop.evaluate(pois).effective_ids, {7})
        initial_pos = tuple(drone.coords)
        initial_propulsion = drone.propulsion_energy
        for end_us in range(1_200_001, 3_100_002, 100_000):
            previous = tuple(drone.coords)
            sim.env.run(until=end_us)
            self.assertLessEqual(dist(previous, drone.coords), 2.000001)
            self.assertEqual(drone.mobility_model.last_update_us, end_us - 1)
            self.assertEqual(loop.adapter.capture().snapshot_time_us,
                             end_us // 1_000_000 * 1_000_000)
            if end_us == 2_200_001:
                node = loop.adapter.capture().nodes[1]
                self.assertTrue(node.planned_path_available)
                self.assertFalse(node.route_available_now)
                self.assertFalse(loop.evaluate(pois).effective_ids)
        self.assertAlmostEqual(dist(initial_pos, drone.coords), 40)
        self.assertAlmostEqual(drone.propulsion_energy - initial_propulsion,
                               2 * drone.energy_model.power_consumption(20))
        self.assertAlmostEqual(drone.initial_energy - drone.residual_energy,
                               drone.propulsion_energy + drone.communication_energy, places=6)
        after = loop.adapter.capture()
        self.assertGreater(after.epoch, before.epoch)
        self.assertFalse(after.nodes[1].route_available_now)
        result = loop.evaluate(pois)
        self.assertEqual(result.geometric_ids, {7})
        self.assertFalse(result.effective_ids)
        self.assertEqual(result.total_pois, 2)

    def test_empty_opt_in_preserves_default_mobility_and_snapshot(self):
        snapshots = []
        for selection in (None, {}):
            random.seed(2025)
            counters = {key: value for key, value in vars(config).items()
                        if key.startswith("GL_ID_")}
            with patch.multiple(config, PACKET_DIAGNOSTICS=True, **counters):
                sim = self.make_sim(selection)
                sim.env.run(until=2_000_001)
            drone = sim.drones[1]
            state = DeterministicLoop(sim, 50).adapter.capture()
            packets = sim.metrics.packet_diagnostics.packets
            snapshots.append((type(drone.mobility_model), tuple(drone.coords),
                              drone.propulsion_energy, state,
                              [(pid, row["creation_time"], row["delivered_time"])
                               for pid, row in packets.items()]))
        self.assertEqual(*snapshots)

    def test_mixed_mobility_and_replay_is_rejected_before_start(self):
        with patch.multiple(config, NUMBER_OF_DRONES=3, MOBILITY_MODEL="GaussMarkov3D"), patch(
                "simulator.simulator.start_coords.get_random_start_point_3d",
                return_value=[(500, 500, 150), (600, 500, 150), (520, 500, 150)]):
            sim = self.make_sim({1: MovementLimits(100, 20)}, count=3)
            self.assertIsInstance(sim.drones[1].mobility_model, MovementController)
            self.assertIsInstance(sim.drones[2].mobility_model, GaussMarkov3D)
            sim.env.run(until=300_001)
            self.assertEqual(sim.drones[1].coords, [600, 500, 150])
        with patch.object(config, "MOBILITY_TRACE_MODE", "replay"):
            with self.assertRaisesRegex(ValueError, "requires live"):
                self.make_sim({1: MovementLimits(100, 20)})

    def test_shared_poi_and_explicit_handoff_on_loss_exit_or_failure(self):
        positions = [(500, 500, 150), (720, 500, 150), (420, 500, 150)]
        for event_type in ("loss", "exit", "failure"):
            with self.subTest(event=event_type), patch.object(config, "NUMBER_OF_DRONES", 3), patch(
                    "simulator.simulator.start_coords.get_random_start_point_3d",
                    return_value=positions):
                sim = self.make_sim({i: MovementLimits(100, 20) for i in (1, 2)}, count=3)
                loop = DeterministicLoop(sim, 155)
                sim.env.run(until=1_000_001)
                sim.env.run(until=sim.env.timeout(99_999))
                loop.decide({1: {7}, 2: {7}}, {}, 2_000_000)
                self.assertEqual(set(loop.assignments), {1, 2})
                pois = {7: (570, 500, 150)}
                self.assertEqual(loop.evaluate(pois).effective_ids, {7})

                sim.env.run(until=1_100_001)
                sim.env.run(until=sim.env.timeout(99_999))
                if event_type == "failure":
                    sim.drones[1].sleep = True
                elif event_type == "loss":
                    # Fault fixture invalidates the published route's geometry.
                    sim.drones[1].coords = (950, 500, 150)
                candidates = {2: {7}} if event_type == "exit" else {1: {7}, 2: {7}}
                if event_type != "exit":
                    # The backup may depend on the old CH. Let Part1 publish a
                    # fresh path before expecting the backup to provide coverage.
                    sim.env.run(until=2_000_001)
                    sim.env.run(until=sim.env.timeout(99_999))
                loop.decide(candidates, {}, 2_000_000)
                self.assertEqual(loop.assignments, {2: frozenset({7})})
                self.assertEqual(loop.evaluate(pois).effective_ids, {7})

    def test_failed_shared_head_does_not_count_false_coverage(self):
        with patch.object(config, "NUMBER_OF_DRONES", 3), patch(
                "simulator.simulator.start_coords.get_random_start_point_3d",
                return_value=[(500, 500, 150), (700, 500, 150), (590, 500, 150)]):
            sim = self.make_sim({i: MovementLimits(100, 20) for i in (1, 2)}, count=3)
            loop = DeterministicLoop(sim, 100)
            sim.env.run(until=1_000_001)
            sim.env.run(until=sim.env.timeout(99_999))
            self.assertIn(1, loop.adapter.capture().nodes[2].planned_path_to_bs)
            loop.decide({1: {7}, 2: {7}}, {}, 2_000_000)
            sim.drones[1].sleep = True
            sim.env.run(until=2_000_001)
            sim.env.run(until=sim.env.timeout(99_999))
            loop.decide({1: {7}, 2: {7}}, {}, 2_000_000)
            self.assertFalse(loop.evaluate({7: (645, 500, 150)}).effective_ids)

    def test_pdr_uses_unique_packet_outcomes_and_handles_empty_horizon(self):
        rows = [{"packet_id": "1", "outcome": "delivered", "delivery_time": "123"},
                {"packet_id": "2", "outcome": "IncompleteAtHorizon", "delivery_time": ""}]
        self.assertEqual(packet_counts(rows)["packet_delivery_ratio"], 0.5)
        self.assertIsNone(packet_counts([])["packet_delivery_ratio"])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            packet_counts(rows + rows)

    def test_action_clips_speed_and_distance_for_candidate_periods(self):
        sim = self.make_sim({1: MovementLimits(80, 20)})
        controller = sim.drones[1].mobility_model
        for duration, distance in ((2, 40), (3, 60), (5, 80)):
            self.assertEqual(controller.set_action(0, 1_000, duration * 1_000_000), distance)
        with self.assertRaises(ValueError):
            controller.set_action(0, 1, 100_001)
        with self.assertRaises(ValueError):
            controller.set_action(float("nan"), 1, 100_000)


if __name__ == "__main__":
    unittest.main()
