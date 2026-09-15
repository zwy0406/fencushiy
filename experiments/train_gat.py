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
    raise RuntimeError('PyTorch is required for train_gat.py') from exc

from models.gat_model import GATEncoder
from utils import config


def _split_indices(sample_count, groups=None, seed=2025, train_ratio=0.7, val_ratio=0.15):
    if groups is None:
        groups = np.arange(sample_count)
    unique_groups = np.unique(groups)
    rng = np.random.default_rng(seed)
    rng.shuffle(unique_groups)
    train_end = max(1, int(len(unique_groups) * train_ratio))
    val_end = min(len(unique_groups), max(train_end + 1, int(len(unique_groups) * (train_ratio + val_ratio))))
    train_groups = unique_groups[:train_end]
    val_groups = unique_groups[train_end:val_end]
    test_groups = unique_groups[val_end:]
    if len(val_groups) == 0:
        val_groups = train_groups[-1:]
    if len(test_groups) == 0:
        test_groups = val_groups[-1:]
    return tuple(np.flatnonzero(np.isin(groups, selected)) for selected in (train_groups, val_groups, test_groups))


def _batch_loss(model, batch_x, batch_adj, batch_y, criterion, device):
    losses = []
    for sample_x, sample_adj, sample_y in zip(batch_x, batch_adj, batch_y):
        prediction, _ = model(sample_x.to(device), sample_adj.to(device))
        losses.append(criterion(prediction, sample_y.to(device)))
    return torch.stack(losses).mean()


def _predict(model, loader, device):
    outputs = []
    model.eval()
    with torch.no_grad():
        for batch_x, batch_adj, _ in loader:
            outputs.extend(
                model(sample_x.to(device), sample_adj.to(device))[0].cpu().numpy()
                for sample_x, sample_adj in zip(batch_x, batch_adj)
            )
    return np.asarray(outputs)


def _metrics(predictions, references):
    return {
        'rmse': float(np.sqrt(np.mean((predictions - references) ** 2))),
        'mae': float(np.mean(np.abs(predictions - references))),
    }


def train(dataset_path, model_path, config_path, epochs=80, batch_size=32,
          lr=1e-3, split_seed=2025, patience=12, device_name='auto'):
    random.seed(split_seed)
    np.random.seed(split_seed)
    torch.manual_seed(split_seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(split_seed)

    dataset = np.load(dataset_path)
    features = dataset['features'].astype(np.float32)
    adjacency = dataset['adjacency'].astype(np.float32)
    labels = dataset['labels'].astype(np.float32)
    if len(features) == 0:
        raise ValueError('No graph samples found in dataset.')
    groups = dataset['scenario_ids'] if 'scenario_ids' in dataset.files else None
    train_idx, val_idx, test_idx = _split_indices(len(features), groups, split_seed)
    feature_mean = features[train_idx].mean(axis=(0, 1))
    feature_std = features[train_idx].std(axis=(0, 1))
    feature_std = np.where(feature_std == 0.0, 1.0, feature_std)
    normalized = (features - feature_mean) / feature_std
    device = torch.device('cuda' if device_name == 'auto' and torch.cuda.is_available() else
                          'cpu' if device_name == 'auto' else device_name)

    loaders = []
    for indices, shuffle in ((train_idx, True), (val_idx, False), (test_idx, False)):
        loaders.append(DataLoader(
            TensorDataset(
                torch.tensor(normalized[indices]),
                torch.tensor(adjacency[indices]),
                torch.tensor(labels[indices]),
            ),
            batch_size=batch_size,
            shuffle=shuffle,
            pin_memory=device.type == 'cuda',
        ))
    train_loader, val_loader, test_loader = loaders
    model = GATEncoder(
        input_dim=features.shape[-1],
        hidden_dim=config.GAT_HIDDEN_DIM,
        embed_dim=config.GAT_EMBED_DIM,
        heads=config.GAT_HEADS,
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
        for batch_x, batch_adj, batch_y in train_loader:
            optimizer.zero_grad()
            loss = _batch_loss(model, batch_x, batch_adj, batch_y, criterion, device)
            loss.backward()
            optimizer.step()
        model.eval()
        losses = []
        with torch.no_grad():
            for batch_x, batch_adj, batch_y in val_loader:
                losses.append(float(_batch_loss(model, batch_x, batch_adj, batch_y, criterion, device)))
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
    predictions = _predict(model, test_loader, device)
    gat_metrics = _metrics(predictions, labels[test_idx])
    degree_metrics = _metrics(features[test_idx, :, 2], labels[test_idx])
    global_mean = float(labels[train_idx].mean())
    mean_metrics = _metrics(np.full_like(labels[test_idx], global_mean), labels[test_idx])
    improvement = 100.0 * (degree_metrics['rmse'] - gat_metrics['rmse']) / degree_metrics['rmse']
    metadata = {
        'input_dim': int(features.shape[-1]),
        'hidden_dim': config.GAT_HIDDEN_DIM,
        'embed_dim': config.GAT_EMBED_DIM,
        'heads': config.GAT_HEADS,
        'dropout': 0.1,
        'feature_mean': feature_mean.tolist(),
        'feature_std': feature_std.tolist(),
        'samples': int(len(features)),
        'scenarios': int(len(np.unique(groups))) if groups is not None else int(len(features)),
        'split_seed': split_seed,
        'split_samples': {'train': len(train_idx), 'val': len(val_idx), 'test': len(test_idx)},
        'best_epoch': best_epoch,
        'device': str(device),
        'gat': gat_metrics,
        'degree_baseline': degree_metrics,
        'global_mean_baseline': mean_metrics,
        'label_mean': global_mean,
        'rmse_improvement_vs_degree_pct': float(improvement),
    }
    with open(config_path, 'w', encoding='utf-8') as stream:
        json.dump(metadata, stream, indent=2)
    return {'model_path': model_path, 'config_path': config_path, **metadata}


def main():
    parser = argparse.ArgumentParser(description='Train graph-stability GAT for GA-MP-DCA')
    parser.add_argument('--dataset', default=os.path.join(config.DATA_DIR, 'graph_corpus', 'graph_dataset.npz'))
    parser.add_argument('--model-path', default=os.path.join('models', 'gat', 'candidate_stability.pt'))
    parser.add_argument('--config-path', default=os.path.join('models', 'config', 'gat_candidate_stability.json'))
    parser.add_argument('--epochs', type=int, default=80)
    parser.add_argument('--batch-size', type=int, default=32)
    parser.add_argument('--lr', type=float, default=1e-3)
    parser.add_argument('--split-seed', type=int, default=2025)
    parser.add_argument('--patience', type=int, default=12)
    parser.add_argument('--device', default='auto')
    args = parser.parse_args()
    result = train(args.dataset, args.model_path, args.config_path, args.epochs,
                   args.batch_size, args.lr, args.split_seed, args.patience, args.device)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
