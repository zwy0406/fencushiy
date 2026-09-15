from utils import config


class ClusterRotationManager:
    def should_rotate(self, current_head, candidate_head, stable_rounds):
        if current_head is None or candidate_head is None:
            return True

        energy_ratio = current_head.residual_energy / float(config.INITIAL_ENERGY)
        if energy_ratio <= config.CH_MIN_ENERGY_RATIO:
            return True

        round_limit = max(1, int(config.CH_MAX_LIFETIME / max(1, config.CLUSTER_INTERVAL)))
        if getattr(current_head, 'cluster_age', 0) >= round_limit:
            return True

        current_tlet = getattr(current_head, 'avg_let', 0.0)
        if not getattr(config, 'ADAPTIVE_CH_ROTATION', False):
            if current_tlet <= config.PREDICTION_HORIZON * config.CH_LET_DROP_RATIO:
                return True

            if getattr(current_head, 'mobility_factor', 0.0) >= config.CH_MOBILITY_ROTATION_THRESHOLD:
                return True

            if len(getattr(current_head, 'cluster_members', [])) > config.CH_MAX_LOAD:
                return True

            if getattr(candidate_head, 'cluster_weight', 0.0) - getattr(current_head, 'cluster_weight', 0.0) >= config.CH_ROTATION_WEIGHT_MARGIN and stable_rounds >= config.CH_ROTATION_STABLE_ROUNDS:
                return True

            return False

        if len(getattr(current_head, 'cluster_members', [])) > config.CH_MAX_LOAD:
            return True

        horizon = max(1.0, float(config.PREDICTION_HORIZON))
        current_tlet_ratio = max(0.0, min(1.0, current_tlet / horizon))
        candidate_tlet = getattr(candidate_head, 'avg_let', 0.0)
        candidate_tlet_ratio = max(0.0, min(1.0, candidate_tlet / horizon))
        score_gain = (
            getattr(candidate_head, 'cluster_weight', 0.0) -
            getattr(current_head, 'cluster_weight', 0.0)
        )

        low_tlet = current_tlet_ratio <= config.CH_LET_DROP_RATIO
        tlet_gain = candidate_tlet_ratio - current_tlet_ratio
        if (
            low_tlet and
            tlet_gain >= config.CH_ROTATION_TLET_GAIN_MARGIN and
            score_gain >= -config.CH_ROTATION_SCORE_LOSS_TOLERANCE
        ):
            return True

        current_mobility = getattr(current_head, 'mobility_factor', 0.0)
        candidate_mobility = getattr(candidate_head, 'mobility_factor', 0.0)
        if (
            current_mobility >= config.CH_MOBILITY_ROTATION_THRESHOLD and
            candidate_mobility < current_mobility and
            score_gain >= -config.CH_ROTATION_SCORE_LOSS_TOLERANCE
        ):
            return True

        required_margin = (
            config.CH_ROTATION_WEIGHT_MARGIN +
            config.CH_ROTATION_STABILITY_MARGIN_BONUS * current_tlet_ratio
        )
        if score_gain >= required_margin and stable_rounds >= config.CH_ROTATION_STABLE_ROUNDS:
            return True

        return False
