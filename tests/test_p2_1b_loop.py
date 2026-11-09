import unittest
from math import dist
from unittest.mock import patch

import simpy

from part2.integration.deterministic_loop import DeterministicLoop, DeterministicSimulator
from part2.integration.movement_controller import MovementController, MovementLimits
from simulator.simulator import Simulator
from utils import config


class DeterministicLoopTest(unittest.TestCase):
    def setUp(self):
        options = dict(NUMBER_OF_DRONES=2, USE_BASE_STATION=True, BS_NODE_ID=0,
                       BS_POSITION=(500, 500, 150), ROUTING_PROTOCOL="MWMP_DCA",
                       ENABLE_VISUALIZATION=False, ENABLE_PLOTS=False,
                       ENABLE_POI=False, TRACE_ONLY=False, MOBILITY_TRACE_MODE="live",
                       HETEROGENEOUS=False, ENABLE_CLUSTER_SNAPSHOT_LOGGING=False)
        self.enterContext(patch.multiple(config, **options))
        self.enterContext(patch("simulator.simulator.start_coords.get_random_start_point_3d",
                                return_value=[(500, 500, 150), (730, 500, 150)]))

    def make_sim(self, controlled=None):
        env = simpy.Environment()
        channels = {i: simpy.Resource(env, capacity=1) for i in range(2)}
        kwargs = dict(seed=2025, env=env, channel_states=channels, n_drones=2,
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
            sim = self.make_sim(selection)
            sim.env.run(until=2_000_001)
            drone = sim.drones[1]
            state = DeterministicLoop(sim, 50).adapter.capture()
            snapshots.append((type(drone.mobility_model), tuple(drone.coords),
                              drone.propulsion_energy, state))
        self.assertEqual(*snapshots)

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
