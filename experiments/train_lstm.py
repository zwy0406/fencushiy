import argparse
import json
import os
import random
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except ImportError as exc:  # pragma: no cover
    raise RuntimeError('PyTorch is required for train_lstm.py') from exc

from models.lstm_model import TrajectoryLSTM
from utils import config


def _split_indices(sample_count, groups=None, seed=2025, train_ratio=0.7, val_ratio=0.15):
    if groups is None:
        groups = np.arange(sample_count)
    unique_groups = np.unique(groups)
    rng = np.random.default_rng(seed)
    rng.shuffle(unique_groups)
    train_end = max(1, int(len(unique_groups) * train_ratio))
    val_end = max(train_end + 1, int(len(unique_groups) * (train_ratio + val_ratio)))
    val_end = min(val_end, len(unique_groups))
    train_groups = unique_groups[:train_end]
    val_groups = unique_groups[train_end:val_end]
    test_groups = unique_groups[val_end:]
    if len(val_groups) == 0:
        val_groups = train_groups[-1:]
    if len(test_groups) == 0:
        test_groups = val_groups[-1:]
    return (
        np.flatnonzero(np.isin(groups, train_groups)),
        np.flatnonzero(np.isin(groups, val_groups)),
        np.flatnonzero(np.isin(groups, test_groups)),
    )


def _normalize(data, mean=None, std=None):
    if mean is None:
        mean = data.mean(axis=(0, 1))
    if std is None:
        std = data.std(axis=(0, 1))
    std = np.where(std == 0.0, 1.0, std)
    return (data - mean) / std, mean, std


def _kinematic_forecast(inputs, horizon):
    steps = np.arange(1, horizon + 1, dtype=np.float32).reshape(1, horizon, 1)
    return inputs[:, -1:, :3] + inputs[:, -1:, 3:6] * steps


def _meter_metrics(predictions, references):
    distances = np.linalg.norm(predictions - references, axis=-1)
    return {
        'rmse_m': float(np.sqrt(np.mean(distances ** 2))),
        'mae_m': float(np.mean(distances)),
        'ade_m': float(np.mean(distances)),
        'fde_m': float(np.mean(distances[:, -1])),
    }


def _predict(model, loader, device):
    outputs = []
    model.eval()
    with torch.no_grad():
        for batch_x, _ in loader:
            outputs.append(model(batch_x.to(device)).cpu().numpy())
    return np.concatenate(outputs, axis=0)


def train(dataset_path, model_path, config_path, epochs=80, batch_size=256,
          lr=1e-3, split_seed=2025, target_mode='kinematic_residual', patience=12,
          device_name='auto'):
    random.seed(split_seed)
    np.random.seed(split_seed)
    torch.manual_seed(split_seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(split_seed)

    dataset = np.load(dataset_path)
    inputs = dataset['inputs'].astype(np.float32)
    targets = dataset['targets'].astype(np.float32)
    if len(inputs) == 0:
        raise ValueError('No trajectory samples found in dataset.')
    groups = dataset['track_ids'] if 'track_ids' in dataset.files else None
    train_idx, val_idx, test_idx = _split_indices(len(inputs), groups, split_seed)
    horizon = targets.shape[1]
    kinematic = _kinematic_forecast(inputs, horizon)
    learning_targets = targets - kinematic if target_mode == 'kinematic_residual' else targets

    x_train, feature_mean, feature_std = _normalize(inputs[train_idx])
    x_val, _, _ = _normalize(inputs[val_idx], feature_mean, feature_std)
    x_test, _, _ = _normalize(inputs[test_idx], feature_mean, feature_std)
    y_train, target_mean, target_std = _normalize(learning_targets[train_idx])
    y_val, _, _ = _normalize(learning_targets[val_idx], target_mean, target_std)
    y_test, _, _ = _normalize(learning_targets[test_idx], target_mean, target_std)

    device = torch.device('cuda' if device_name == 'auto' and torch.cuda.is_available() else
                          'cpu' if device_name == 'auto' else device_name)
    loaders = []
    for x_values, y_values, shuffle in ((x_train, y_train, True), (x_val, y_val, False), (x_test, y_test, False)):
        loaders.append(DataLoader(
            TensorDataset(torch.tensor(x_values), torch.tensor(y_values)),
            batch_size=batch_size,
            shuffle=shuffle,
            pin_memory=device.type == 'cuda',
        ))
    train_loader, val_loader, test_loader = loaders

    model = TrajectoryLSTM(
        input_dim=inputs.shape[-1],
        hidden_dim=config.LSTM_HIDDEN_DIM,
        num_layers=config.LSTM_LAYERS,
        horizon=horizon,
        output_dim=targets.shape[-1],
    ).to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    best_val = float('inf')
    best_epoch = 0
    stale_epochs = 0

    for epoch in range(1, epochs + 1):
        model.train()
        for batch_x, batch_y in train_loader:
            optimizer.zero_grad()
            loss = criterion(model(batch_x.to(device)), batch_y.to(device))
            loss.backward()
            optimizer.step()
        model.eval()
        losses = []
        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                losses.append(criterion(model(batch_x.to(device)), batch_y.to(device)).item())
        val_loss = float(np.mean(losses))
        if val_loss < best_val:
            best_val, best_epoch, stale_epochs = val_loss, epoch, 0
            torch.save(model.state_dict(), model_path)
        else:
            stale_epochs += 1
        if epoch == 1 or epoch % 10 == 0:
            print(f'epoch={epoch} val_mse={val_loss:.6f} best={best_val:.6f}')
        if stale_epochs >= patience:
            break

    model.load_state_dict(torch.load(model_path, map_location=device))
    normalized_predictions = _predict(model, test_loader, device)
    learned_predictions = normalized_predictions * target_std + target_mean
    predictions = learned_predictions + kinematic[test_idx] if target_mode == 'kinematic_residual' else learned_predictions
    lstm_metrics = _meter_metrics(predictions, targets[test_idx])
    kinematic_metrics = _meter_metrics(kinematic[test_idx], targets[test_idx])
    improvement = 100.0 * (kinematic_metrics['rmse_m'] - lstm_metrics['rmse_m']) / kinematic_metrics['rmse_m']
    mean_prediction = np.broadcast_to(targets[train_idx].mean(axis=0), targets[test_idx].shape)
    mean_metrics = _meter_metrics(mean_prediction, targets[test_idx])

    metadata = {
        'input_dim': int(inputs.shape[-1]),
        'hidden_dim': config.LSTM_HIDDEN_DIM,
        'num_layers': config.LSTM_LAYERS,
        'horizon': int(horizon),
        'output_dim': int(targets.shape[-1]),
        'dropout': 0.1,
        'target_mode': target_mode,
        'feature_mean': feature_mean.tolist(),
        'feature_std': feature_std.tolist(),
        'target_mean': target_mean.tolist(),
        'target_std': target_std.tolist(),
        'samples': int(len(inputs)),
        'tracks': int(len(np.unique(groups))) if groups is not None else int(len(inputs)),
        'split_seed': split_seed,
        'split_samples': {'train': len(train_idx), 'val': len(val_idx), 'test': len(test_idx)},
        'best_epoch': best_epoch,
        'device': str(device),
        'lstm': lstm_metrics,
        'kinematic': kinematic_metrics,
        'target_mean_baseline': mean_metrics,
        'rmse_improvement_vs_kinematic_pct': float(improvement),
    }
    with open(config_path, 'w', encoding='utf-8') as stream:
        json.dump(metadata, stream, indent=2)
    return {'model_path': model_path, 'config_path': config_path, **metadata}


def main():
    parser = argparse.ArgumentParser(description='Train trajectory LSTM for GA-MP-DCA')
    parser.add_argument('--dataset', default=os.path.join(config.DATA_DIR, 'trajectory_corpus', 'trajectory_dataset.npz'))
    parser.add_argument('--model-path', default=os.path.join('models', 'lstm', 'candidate_residual.pt'))
    parser.add_argument('--config-path', default=os.path.join('models', 'config', 'lstm_candidate_residual.json'))
    parser.add_argument('--epochs', type=int, default=80)
    parser.add_argument('--batch-size', type=int, default=256)
    parser.add_argument('--lr', type=float, default=1e-3)
    parser.add_argument('--split-seed', type=int, default=2025)
    parser.add_argument('--target-mode', choices=('absolute', 'kinematic_residual'), default='kinematic_residual')
    parser.add_argument('--patience', type=int, default=12)
    parser.add_argument('--device', default='auto')
    args = parser.parse_args()
    result = train(args.dataset, args.model_path, args.config_path, args.epochs,
                   args.batch_size, args.lr, args.split_seed, args.target_mode,
                   args.patience, args.device)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
