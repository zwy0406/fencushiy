import torch
from torch import nn


class TrajectoryLSTM(nn.Module):
    def __init__(self, input_dim=6, hidden_dim=64, num_layers=2, horizon=5, output_dim=3, dropout=0.1):
        super().__init__()
        self.horizon = horizon
        self.output_dim = output_dim
        self.encoder = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, horizon * output_dim),
        )

    def forward(self, sequence):
        encoded, _ = self.encoder(sequence)
        last_hidden = encoded[:, -1, :]
        forecast = self.head(last_hidden)
        return forecast.view(-1, self.horizon, self.output_dim)
