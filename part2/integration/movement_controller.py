"""Deterministic horizontal movement for the opt-in Part2 simulator."""

from dataclasses import dataclass
from math import cos, dist, isfinite, sin


@dataclass(frozen=True)
class MovementLimits:
    max_distance_m: float
    max_speed_mps: float
    step_us: int = 100_000

    def __post_init__(self):
        if any(not isfinite(v) or v <= 0
               for v in (self.max_distance_m, self.max_speed_mps)):
            raise ValueError("movement limits must be finite and positive")
        if type(self.step_us) is not int or self.step_us <= 0:
            raise ValueError("step_us must be a positive integer")


class MovementController:
    """The sole coordinate writer for one opted-in Drone."""

    def __init__(self, drone, limits, bounds_xy):
        self.drone = drone
        self.limits = limits
        self.bounds_xy = tuple(bounds_xy)
        self.last_update_us = drone.env.now
        self._velocity_xy = (0.0, 0.0)
        self._expires_us = self.last_update_us
        self._publish_velocity((0.0, 0.0, 0.0))
        drone.env.process(self._run())

    def validate_action(self, heading_rad, distance_m, duration_us):
        if self.drone.env.now != self.last_update_us:
            raise ValueError("issue actions after the movement tick at the current time")
        if not isfinite(heading_rad) or not isfinite(distance_m) or distance_m < 0:
            raise ValueError("invalid heading or distance")
        if (type(duration_us) is not int or duration_us <= 0
                or duration_us % self.limits.step_us):
            raise ValueError("duration must be a positive multiple of step_us")

    def set_action(self, heading_rad, distance_m, duration_us):
        self.validate_action(heading_rad, distance_m, duration_us)
        seconds = duration_us / 1e6
        distance = min(distance_m, self.limits.max_distance_m,
                       self.limits.max_speed_mps * seconds)
        speed = distance / seconds
        self._velocity_xy = (speed * cos(heading_rad), speed * sin(heading_rad))
        self._expires_us = self.last_update_us + duration_us
        return distance

    def cancel(self):
        self.set_action(0.0, 0.0, self.limits.step_us)

    def _publish_velocity(self, velocity):
        self.drone.velocity = list(velocity)
        self.drone.speed = dist((0, 0, 0), velocity)

    def _run(self):
        drone = self.drone
        seconds = self.limits.step_us / 1e6
        while True:
            yield drone.env.timeout(self.limits.step_us)
            moving = self.last_update_us < self._expires_us
            self.last_update_us = drone.env.now
            if drone.sleep or drone.residual_energy <= 0:
                self._publish_velocity((0.0, 0.0, 0.0))
                continue
            vx, vy = self._velocity_xy if moving else (0.0, 0.0)
            x, y, z = drone.coords
            max_x, max_y = self.bounds_xy
            dx = min(max_x, max(0.0, x + vx * seconds)) - x
            dy = min(max_y, max(0.0, y + vy * seconds)) - y
            speed = dist((0, 0), (dx, dy)) / seconds
            required = drone.energy_model.power_consumption(speed) * seconds
            charged = drone.consume_energy(required, source="propulsion")
            fraction = min(1.0, charged / required) if required > 0 else 1.0
            drone.coords = [x + dx * fraction, y + dy * fraction, z]
            velocity = (dx / seconds, dy / seconds, 0.0)
            self._publish_velocity((0.0, 0.0, 0.0) if drone.sleep else velocity)
