import unittest

import numpy as np

try:
    from experiments.train_lstm import _kinematic_forecast, _split_indices
    TRAINING_IMPORT_ERROR = None
except (ImportError, RuntimeError) as exc:  # local environments may omit PyTorch
    TRAINING_IMPORT_ERROR = exc


@unittest.skipIf(TRAINING_IMPORT_ERROR is not None, 'PyTorch training dependencies unavailable')
class TrajectoryTrainingTests(unittest.TestCase):
    def test_group_split_has_no_track_leakage(self):
        groups = np.repeat(np.arange(20), 4)
        train, validation, test = _split_indices(len(groups), groups, seed=17)
        train_groups = set(groups[train])
        validation_groups = set(groups[validation])
        test_groups = set(groups[test])
        self.assertFalse(train_groups & validation_groups)
        self.assertFalse(train_groups & test_groups)
        self.assertFalse(validation_groups & test_groups)

    def test_kinematic_forecast_uses_one_second_steps(self):
        inputs = np.zeros((1, 3, 6), dtype=np.float32)
        inputs[0, -1] = [10, 20, 30, 2, -1, 0.5]
        forecast = _kinematic_forecast(inputs, 2)
        np.testing.assert_allclose(forecast[0, 0], [12, 19, 30.5])
        np.testing.assert_allclose(forecast[0, 1], [14, 18, 31])


if __name__ == '__main__':
    unittest.main()
