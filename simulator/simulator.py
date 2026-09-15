import random
import numpy as np
import matplotlib.pyplot as plt
from phy.channel import Channel
from entities.drone import Drone
from entities.obstacle import SphericalObstacle, CubeObstacle
from entities.poi import Poi
from simulator.metrics import Metrics
from mobility import start_coords
from mobility.poi_mobility import PoiRandomWalk3D, PoiHotspotMigration3D, PoiReferencePointGroupMobility3D
from path_planning.astar import astar
from utils import config
from utils.util_function import grid_map
from allocation.central_controller import CentralController
from topology.mwmp_dca.cluster_manager import ClusterManager
from visualization.static_drawing import scatter_plot, scatter_plot_with_obstacles


class Simulator:
    """
    Description: simulation environment

    Attributes:
        env: simpy environment
        total_simulation_time: discrete time steps, in nanosecond
        n_drones: number of the drones
        channel_states: a dictionary, used to describe the channel usage
        channel: wireless channel
        metrics: Metrics class, used to record the network performance
        drones: a list, contains all drone instances

    Author: Zihao Zhou, eezihaozhou@gmail.com
    Created at: 2024/1/11
    Updated at: 2025/7/8
    """

    def __init__(self,
                 seed,
                 env,
                 channel_states,
                 n_drones,
                 total_simulation_time=None):

        self.env = env
        self.seed = seed
        self.total_simulation_time = total_simulation_time if total_simulation_time is not None else config.SIM_TIME

        self.n_drones = n_drones  # total number of drones in the simulation
        self.channel_states = channel_states
        self.channel = Channel(self.env)

        self.metrics = Metrics(self)  # use to record the network performance

        # NOTE: if distributed optimization is adopted, remember to comment this to speed up simulation
        # self.central_controller = CentralController(self)

        start_position = start_coords.get_random_start_point_3d(seed)
        # start_position = start_coords.get_customized_start_point_3d()

        self.drones = []
        self.pois = []
        if config.ENABLE_VISUALIZATION:
            print('Seed is: ', self.seed)
        for i in range(n_drones):
            is_base_station = config.ROUTING_PROTOCOL == 'MWMP_DCA' and i == config.BS_NODE_ID
            if is_base_station:
                coords = config.BS_POSITION
                speed = 0
            elif config.HETEROGENEOUS:
                speed = random.randint(5, 60)
                coords = start_position[i]
            else:
                speed = config.DEFAULT_UAV_SPEED
                coords = start_position[i]

            if config.ENABLE_VISUALIZATION:
                print('UAV: ', i, ' initial location is at: ', coords, ' speed is: ', speed)
            drone = Drone(env=env,
                          node_id=i,
                          coords=coords,
                          speed=speed,
                          inbox=self.channel.create_inbox_for_receiver(i),
                          simulator=self,
                          is_base_station=is_base_station)

            self.drones.append(drone)

        self.cluster_manager = ClusterManager(self) if config.ROUTING_PROTOCOL == 'MWMP_DCA' else None

        if config.ENABLE_POI:
            self._create_pois()

        if config.ENABLE_PLOTS:
            # scatter_plot_with_spherical_obstacles(self)
            scatter_plot(self)

        self.env.process(self.show_performance())
        self.env.process(self.show_time())
        self.env.process(self.monitor_network_metrics())
        if config.ENABLE_POI:
            self.env.process(self.monitor_poi_metrics())

    def show_time(self):
        while True:
            if config.ENABLE_VISUALIZATION:
                print('At time: ', self.env.now / 1e6, ' s.')

            # the simulation process is displayed every 0.5s
            yield self.env.timeout(0.5*1e6)

    def show_performance(self):
        yield self.env.timeout(self.total_simulation_time - 1)

        if config.ENABLE_PLOTS:
            scatter_plot(self)

        if config.ENABLE_POI:
            self.metrics.update_poi_metrics(self)
        self.metrics.print_metrics()
        self.metrics.export_results(config.RESULTS_DIR)

    def _create_pois(self):
        rng = random.Random(self.seed + 2024)
        for poi_id in range(config.POI_COUNT):
            coords = (
                rng.uniform(0, config.MAP_LENGTH),
                rng.uniform(0, config.MAP_WIDTH),
                rng.uniform(0, config.MAP_HEIGHT),
            )
            speed = random.choice(config.POI_SPEED_LIST) if hasattr(config, 'POI_SPEED_LIST') else 0
            poi = Poi(poi_id, coords, speed=speed)
            self.pois.append(poi)

            if config.POI_MOVEMENT_MODEL == 'HotspotMigration':
                PoiHotspotMigration3D(poi, self.env, seed=self.seed + poi_id)
            elif config.POI_MOVEMENT_MODEL == 'ReferencePointGroupMobility':
                PoiReferencePointGroupMobility3D(poi, self.env, seed=self.seed + poi_id)
            else:
                PoiRandomWalk3D(poi, self.env, seed=self.seed + poi_id)

    def monitor_poi_metrics(self):
        while True:
            self.metrics.update_poi_metrics(self)
            yield self.env.timeout(1 * 1e6)

    def monitor_network_metrics(self):
        while True:
            self.metrics.record_timeseries()
            yield self.env.timeout(1 * 1e6)
