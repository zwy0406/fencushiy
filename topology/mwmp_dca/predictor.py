from utils import config
from utils.util_function import euclidean_distance_3d
from models.infer_models import OnlineModelSuite


def _clip_position(position):
    return (
        min(max(position[0], 0), config.MAP_LENGTH),
        min(max(position[1], 0), config.MAP_WIDTH),
        min(max(position[2], 0), config.MAP_HEIGHT),
    )


class KinematicTrajectoryPredictor:
    def predict(self, drone, horizon_seconds=None):
        horizon_seconds = horizon_seconds or config.PREDICTION_HORIZON
        x, y, z = drone.coords
        vx, vy, vz = drone.velocity
        predictions = []

        for t in range(1, horizon_seconds + 1):
            predictions.append(_clip_position((x + vx * t, y + vy * t, z + vz * t)))

        return predictions

    def predict_from_state(self, coords, velocity, horizon_seconds=None):
        horizon_seconds = horizon_seconds or config.PREDICTION_HORIZON
        predictions = []
        for t in range(1, horizon_seconds + 1):
            predictions.append(_clip_position((
                coords[0] + velocity[0] * t,
                coords[1] + velocity[1] * t,
                coords[2] + velocity[2] * t,
            )))
        return predictions

    def evaluate_recent(self, drone, horizon_seconds=None):
        history = getattr(drone, 'trajectory_history', [])
        horizon_seconds = horizon_seconds or config.PREDICTION_HORIZON
        if len(history) <= horizon_seconds + 1:
            return None

        anchor = history[-horizon_seconds - 1]
        actual = [item['coords'] for item in history[-horizon_seconds:]]
        predicted = self.predict_from_state(anchor['coords'], anchor['velocity'], horizon_seconds=horizon_seconds)
        return prediction_error(predicted, actual)


class LstmTrajectoryPredictor(KinematicTrajectoryPredictor):
    def __init__(self, model=None):
        self.model = model or OnlineModelSuite().trajectory_model

    def predict(self, drone, horizon_seconds=None):
        horizon_seconds = horizon_seconds or config.PREDICTION_HORIZON
        if not config.USE_LSTM_PREDICTOR:
            return super().predict(drone, horizon_seconds=horizon_seconds)
        history = getattr(drone, 'trajectory_history', [])
        if len(history) < max(3, config.TRAJECTORY_HISTORY_SIZE):
            return super().predict(drone, horizon_seconds=horizon_seconds)

        sequence = self._sequence_from_history(history)
        predicted = self.model.predict(sequence) if self.model is not None else None
        if predicted:
            config.MODEL_STATUS['lstm'] = getattr(self.model, 'status', 'loaded')
            return [_clip_position(step) for step in predicted[:horizon_seconds]]

        config.MODEL_STATUS['lstm'] = f"fallback:{getattr(self.model, 'status', 'unavailable')}"
        if config.ALLOW_MODEL_FALLBACK:
            coords = history[-1]['coords']
            velocity = self._gated_velocity(history)
            return self.predict_from_state(coords, velocity, horizon_seconds=horizon_seconds)
        return []

    def predict_from_state(self, coords, velocity, horizon_seconds=None, history=None):
        horizon_seconds = horizon_seconds or config.PREDICTION_HORIZON
        if history and config.USE_LSTM_PREDICTOR:
            sequence = self._sequence_from_history(history)
            predicted = self.model.predict(sequence) if self.model is not None else None
            if predicted:
                return [_clip_position(step) for step in predicted[:horizon_seconds]]
        return super().predict_from_state(coords, velocity, horizon_seconds=horizon_seconds)

    def evaluate_recent(self, drone, horizon_seconds=None):
        history = getattr(drone, 'trajectory_history', [])
        horizon_seconds = horizon_seconds or config.PREDICTION_HORIZON
        if len(history) <= horizon_seconds + 3:
            return None

        anchor_idx = len(history) - horizon_seconds - 1
        anchor = history[anchor_idx]
        past = history[:anchor_idx + 1]
        actual = [item['coords'] for item in history[-horizon_seconds:]]
        predicted = self.predict_from_state(
            anchor['coords'],
            self._gated_velocity(past),
            horizon_seconds=horizon_seconds,
            history=past,
        )
        return prediction_error(predicted, actual)

    def _sequence_from_history(self, history):
        window = history[-config.TRAJECTORY_HISTORY_SIZE:]
        sequence = []
        for item in window:
            sequence.append([
                item['coords'][0],
                item['coords'][1],
                item['coords'][2],
                item['velocity'][0],
                item['velocity'][1],
                item['velocity'][2],
            ])
        if sequence and len(sequence) < config.TRAJECTORY_HISTORY_SIZE:
            sequence = [sequence[0]] * (config.TRAJECTORY_HISTORY_SIZE - len(sequence)) + sequence
        return sequence

    def _gated_velocity(self, history):
        window = history[-config.TRAJECTORY_HISTORY_SIZE:]
        velocities = [item['velocity'] for item in window if 'velocity' in item]
        if not velocities:
            return (0.0, 0.0, 0.0)

        recent = velocities[-1]
        long_term = tuple(sum(v[idx] for v in velocities) / len(velocities) for idx in range(3))
        if len(velocities) >= 2:
            delta = tuple(velocities[-1][idx] - velocities[-2][idx] for idx in range(3))
        else:
            delta = (0.0, 0.0, 0.0)

        update_gate = 0.65
        reset_gate = 0.35
        return tuple(
            update_gate * recent[idx] +
            (1.0 - update_gate) * long_term[idx] +
            reset_gate * delta[idx]
            for idx in range(3)
        )


def prediction_error(predicted, actual):
    horizon = min(len(predicted), len(actual))
    if horizon == 0:
        return None

    distances = [euclidean_distance_3d(predicted[idx], actual[idx]) for idx in range(horizon)]
    mae = sum(distances) / horizon
    rmse = (sum(value ** 2 for value in distances) / horizon) ** 0.5
    return rmse, mae


def build_predictor():
    if config.PREDICTOR_MODE.lower() == 'lstm':
        return LstmTrajectoryPredictor()
    return KinematicTrajectoryPredictor()
