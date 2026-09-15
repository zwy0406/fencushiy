import argparse
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.infer_models import OnlineGraphModel


def _metrics(predictions, references):
    return {
        'rmse': float(np.sqrt(np.mean((predictions - references) ** 2))),
        'mae': float(np.mean(np.abs(predictions - references))),
    }


def evaluate(dataset_path, model_path, config_path):
    dataset = np.load(dataset_path)
    features = dataset['features'].astype(np.float32)
    adjacency = dataset['adjacency'].astype(np.float32)
    labels = dataset['labels'].astype(np.float32)
    speeds = dataset['speeds'] if 'speeds' in dataset.files else np.zeros(len(features))
    model = OnlineGraphModel(model_path, config_path)
    if not model.available:
        raise RuntimeError(f'Unable to load candidate model: {model.status}')
    predictions = np.asarray([
        model.encode(sample_features, sample_adjacency)[0]
        for sample_features, sample_adjacency in zip(features, adjacency)
    ])
    output = {
        'model_status': model.status,
        'samples': len(features),
        'overall': {
            'gat': _metrics(predictions, labels),
            'degree_baseline': _metrics(features[:, :, 2], labels),
        },
        'by_speed': {},
    }
    for speed in np.unique(speeds):
        selected = speeds == speed
        output['by_speed'][str(float(speed))] = {
            'gat': _metrics(predictions[selected], labels[selected]),
            'degree_baseline': _metrics(features[selected, :, 2], labels[selected]),
        }
    degree_rmse = output['overall']['degree_baseline']['rmse']
    gat_rmse = output['overall']['gat']['rmse']
    output['rmse_improvement_vs_degree_pct'] = 100.0 * (degree_rmse - gat_rmse) / degree_rmse
    return output


def main():
    parser = argparse.ArgumentParser(description='Evaluate GAT on independent graph scenarios')
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--model-path', default=os.path.join('models', 'gat', 'candidate_stability.pt'))
    parser.add_argument('--config-path', default=os.path.join('models', 'config', 'gat_candidate_stability.json'))
    parser.add_argument('--output', default=os.path.join('results', 'gat_candidate_replay.json'))
    args = parser.parse_args()
    result = evaluate(args.dataset, args.model_path, args.config_path)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
