import json
import os

import numpy as np

from utils import config

try:
    import torch
except ImportError:  # pragma: no cover - runtime fallback path
    torch = None


def _safe_load_json(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _tensor_or_none():
    return torch is not None


def _resolve_device():
    if not _tensor_or_none():
        return 'cpu', 'torch_missing'

    requested = str(getattr(config, 'MODEL_DEVICE', 'auto')).lower()
    device_index = int(getattr(config, 'CUDA_DEVICE_INDEX', 0))

    if requested == 'cpu':
        return torch.device('cpu'), 'cpu_forced'

    if requested in ('auto', 'gpu', 'cuda') or requested.startswith('cuda'):
        if torch.cuda.is_available():
            if requested.startswith('cuda:'):
                return torch.device(requested), requested
            return torch.device(f'cuda:{device_index}'), f'cuda:{device_index}'
        if requested != 'auto':
            return torch.device('cpu'), 'cuda_unavailable_fallback_cpu'

    return torch.device('cpu'), 'cpu'


class OnlineTrajectoryModel:
    def __init__(self, model_path=None, config_path=None):
        self.model_path = model_path or config.LSTM_MODEL_PATH
        self.config_path = config_path or config.LSTM_CONFIG_PATH
        self.meta = _safe_load_json(self.config_path)
        self.model = None
        self.device, self.device_status = _resolve_device()
        self.available = False
        self.status = 'disabled'
        self._load()

    def _load(self):
        if not _tensor_or_none():
            self.status = 'torch_missing'
            return
        if not os.path.exists(self.model_path):
            self.status = 'checkpoint_missing'
            return

        from models.lstm_model import TrajectoryLSTM

        model = TrajectoryLSTM(
            input_dim=self.meta.get('input_dim', config.LSTM_INPUT_DIM),
            hidden_dim=self.meta.get('hidden_dim', config.LSTM_HIDDEN_DIM),
            num_layers=self.meta.get('num_layers', config.LSTM_LAYERS),
            horizon=self.meta.get('horizon', config.PREDICTION_HORIZON),
            output_dim=self.meta.get('output_dim', 3),
            dropout=self.meta.get('dropout', 0.1),
        )
        state = torch.load(self.model_path, map_location=self.device)
        model.load_state_dict(state)
        model.to(self.device)
        model.eval()
        if getattr(self.device, 'type', 'cpu') == 'cuda':
            torch.backends.cudnn.benchmark = True
        self.model = model
        self.available = True
        self.status = f'loaded@{self.device_status}'

    def predict(self, history_sequence):
        if not self.available or history_sequence is None or len(history_sequence) == 0:
            return None

        history_array = np.asarray(history_sequence, dtype=np.float32)
        mean = np.asarray(self.meta.get('feature_mean', [0.0] * history_array.shape[-1]), dtype=np.float32)
        std = np.asarray(self.meta.get('feature_std', [1.0] * history_array.shape[-1]), dtype=np.float32)
        std = np.where(std == 0.0, 1.0, std)
        normalized = (history_array - mean) / std

        with torch.no_grad():
            tensor = torch.tensor(normalized, dtype=torch.float32, device=self.device).unsqueeze(0)
            predicted = self.model(tensor).squeeze(0).detach().cpu().numpy()

        target_mean = np.asarray(self.meta.get('target_mean', [0.0, 0.0, 0.0]), dtype=np.float32)
        target_std = np.asarray(self.meta.get('target_std', [1.0, 1.0, 1.0]), dtype=np.float32)
        target_std = np.where(target_std == 0.0, 1.0, target_std)
        predicted = predicted * target_std + target_mean
        if self.meta.get('target_mode') == 'kinematic_residual':
            steps = np.arange(1, len(predicted) + 1, dtype=np.float32).reshape(-1, 1)
            kinematic = history_array[-1, :3] + history_array[-1, 3:6] * steps
            predicted = predicted + kinematic
        return [tuple(float(value) for value in step) for step in predicted]


class OnlineGraphModel:
    def __init__(self, model_path=None, config_path=None):
        self.model_path = model_path or config.GAT_MODEL_PATH
        self.config_path = config_path or config.GAT_CONFIG_PATH
        self.meta = _safe_load_json(self.config_path)
        self.model = None
        self.device, self.device_status = _resolve_device()
        self.available = False
        self.status = 'disabled'
        self._load()

    def _load(self):
        if not _tensor_or_none():
            self.status = 'torch_missing'
            return
        if not os.path.exists(self.model_path):
            self.status = 'checkpoint_missing'
            return

        from models.gat_model import GATEncoder

        model = GATEncoder(
            input_dim=self.meta.get('input_dim', config.GRAPH_FEATURE_DIM),
            hidden_dim=self.meta.get('hidden_dim', config.GAT_HIDDEN_DIM),
            embed_dim=self.meta.get('embed_dim', config.GAT_EMBED_DIM),
            heads=self.meta.get('heads', config.GAT_HEADS),
            dropout=self.meta.get('dropout', 0.1),
        )
        state = torch.load(self.model_path, map_location=self.device)
        model.load_state_dict(state)
        model.to(self.device)
        model.eval()
        if getattr(self.device, 'type', 'cpu') == 'cuda':
            torch.backends.cudnn.benchmark = True
        self.model = model
        self.available = True
        self.status = f'loaded@{self.device_status}'

    def encode(self, feature_matrix, adjacency_matrix):
        if not self.available or feature_matrix is None or adjacency_matrix is None:
            return None, None

        feature_array = np.asarray(feature_matrix, dtype=np.float32)
        adjacency_array = np.asarray(adjacency_matrix, dtype=np.float32)
        mean = np.asarray(self.meta.get('feature_mean', [0.0] * feature_array.shape[-1]), dtype=np.float32)
        std = np.asarray(self.meta.get('feature_std', [1.0] * feature_array.shape[-1]), dtype=np.float32)
        std = np.where(std == 0.0, 1.0, std)
        normalized = (feature_array - mean) / std

        with torch.no_grad():
            features = torch.tensor(normalized, dtype=torch.float32, device=self.device)
            adjacency = torch.tensor(adjacency_array, dtype=torch.float32, device=self.device)
            scores, embedding = self.model(features, adjacency)
        return scores.cpu().numpy(), embedding.cpu().numpy()


class OnlineModelSuite:
    def __init__(self):
        self.trajectory_model = OnlineTrajectoryModel()
        self.graph_model = OnlineGraphModel()

    def refresh_status(self):
        config.MODEL_STATUS = {
            'lstm': self.trajectory_model.status,
            'gat': self.graph_model.status,
            'ga_mode': config.CLUSTER_ALGORITHM,
        }
        return config.MODEL_STATUS
