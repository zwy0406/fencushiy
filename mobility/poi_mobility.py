import math
import random
from utils import config


class PoiRandomWalk3D:
    def __init__(self, poi, env, seed=0):
        self.poi = poi
        self.env = env
        self.rng = random.Random(seed)
        self.position_update_interval = 1 * 1e6
        self.env.process(self.run())

    def run(self):
        while True:
            theta = self.rng.uniform(0, 2 * math.pi)
            phi = self.rng.uniform(-math.pi / 6, math.pi / 6)
            speed = self.poi.speed
            self.poi.velocity = [
                speed * math.cos(theta) * math.cos(phi),
                speed * math.sin(theta) * math.cos(phi),
                speed * math.sin(phi),
            ]
            self.poi.coords[0] = min(max(self.poi.coords[0] + self.poi.velocity[0], 0), config.MAP_LENGTH)
            self.poi.coords[1] = min(max(self.poi.coords[1] + self.poi.velocity[1], 0), config.MAP_WIDTH)
            self.poi.coords[2] = min(max(self.poi.coords[2] + self.poi.velocity[2], 0), config.MAP_HEIGHT)
            self.poi.history.append((self.env.now, tuple(self.poi.coords)))
            yield self.env.timeout(self.position_update_interval)


class PoiHotspotMigration3D(PoiRandomWalk3D):
    pass


class PoiReferencePointGroupMobility3D(PoiRandomWalk3D):
    pass

