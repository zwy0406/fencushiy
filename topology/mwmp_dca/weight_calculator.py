import json
import os

from utils import config


def clamp01(value):
    return max(0.0, min(1.0, value))


class WeightCalculator:
    def __init__(self, profile_name=None):
        self.profile_name = profile_name or config.MWMP_WEIGHT_PROFILE
        self.ga_weights = self._load_ga_weights()

    def _profile(self):
        return config.MWMP_WEIGHT_PROFILES[self.profile_name]

    def _load_ga_weights(self):
        if os.path.exists(config.GA_WEIGHT_FILE):
            with open(config.GA_WEIGHT_FILE, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            weights = payload.get('weights', {})
            if weights:
                return weights
        return dict(config.GA_SCORE_WEIGHTS)

    def score(self, energy_ratio, link_quality, density, tlet_ratio, mobility_factor, load_ratio=0.0, poi_ratio=0.0):
        profile = self._profile()
        value = (
            profile.get('energy', 0.0) * clamp01(energy_ratio) +
            profile.get('link_quality', 0.0) * clamp01(link_quality) +
            profile.get('density', 0.0) * clamp01(density) +
            profile.get('tlet', 0.0) * clamp01(tlet_ratio) +
            profile.get('mobility', 0.0) * clamp01(mobility_factor) +
            profile.get('load', 0.0) * clamp01(load_ratio) +
            profile.get('poi', 0.0) * clamp01(poi_ratio)
        )
        if config.USE_POI_AWARE_WEIGHT:
            value += config.POI_WEIGHT * clamp01(poi_ratio)
        return clamp01(value)

    def normalize_link_quality(self, sinr_value):
        return clamp01((sinr_value + 10.0) / 40.0)

    def normalize_density(self, density, max_density):
        if max_density <= 0:
            return 0.0
        return clamp01(density / max_density)

    def normalize_tlet(self, tlet_seconds, horizon_seconds=None):
        horizon_seconds = horizon_seconds or config.PREDICTION_HORIZON
        return clamp01(tlet_seconds / float(horizon_seconds))

    def normalize_mobility(self, displacement_ratio):
        return clamp01(displacement_ratio)

    def normalize_topology(self, topology_score):
        return clamp01(topology_score)

    def ga_score(self, energy_ratio, link_quality, tlet_ratio, topology_score, mobility_factor):
        weights = self.ga_weights
        value = (
            weights.get('w1_energy', 0.0) * clamp01(energy_ratio) +
            weights.get('w2_link_quality', 0.0) * clamp01(link_quality) +
            weights.get('w3_tlet', 0.0) * clamp01(tlet_ratio) +
            weights.get('w4_topology', 0.0) * clamp01(topology_score) -
            weights.get('w5_mobility', 0.0) * clamp01(mobility_factor)
        )
        return clamp01(value)
