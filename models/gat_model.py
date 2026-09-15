import torch
from torch import nn


class GraphAttentionLayer(nn.Module):
    def __init__(self, in_features, out_features, dropout=0.1, alpha=0.2):
        super().__init__()
        self.linear = nn.Linear(in_features, out_features, bias=False)
        self.attn_src = nn.Parameter(torch.empty(out_features))
        self.attn_dst = nn.Parameter(torch.empty(out_features))
        self.leaky_relu = nn.LeakyReLU(alpha)
        self.dropout = nn.Dropout(dropout)
        self.reset_parameters()

    def reset_parameters(self):
        nn.init.xavier_uniform_(self.linear.weight)
        nn.init.xavier_uniform_(self.attn_src.unsqueeze(0))
        nn.init.xavier_uniform_(self.attn_dst.unsqueeze(0))

    def forward(self, features, adjacency):
        projected = self.linear(features)
        src_scores = torch.matmul(projected, self.attn_src)
        dst_scores = torch.matmul(projected, self.attn_dst)
        logits = self.leaky_relu(src_scores.unsqueeze(1) + dst_scores.unsqueeze(0))

        mask = adjacency > 0
        logits = logits.masked_fill(~mask, float('-inf'))
        attention = torch.softmax(logits, dim=1)
        attention = torch.nan_to_num(attention, nan=0.0, posinf=0.0, neginf=0.0)
        attention = self.dropout(attention)
        return torch.matmul(attention, projected)


class GATEncoder(nn.Module):
    def __init__(self, input_dim=4, hidden_dim=16, embed_dim=8, heads=2, dropout=0.1):
        super().__init__()
        self.heads = nn.ModuleList([
            GraphAttentionLayer(input_dim, hidden_dim, dropout=dropout)
            for _ in range(heads)
        ])
        self.merge = nn.Linear(hidden_dim * heads, embed_dim)
        self.activation = nn.ELU()
        self.regressor = nn.Sequential(
            nn.Linear(embed_dim, embed_dim),
            nn.ReLU(),
            nn.Linear(embed_dim, 1),
            nn.Sigmoid(),
        )

    def encode(self, features, adjacency):
        head_outputs = [head(features, adjacency) for head in self.heads]
        merged = torch.cat(head_outputs, dim=-1)
        embedding = self.activation(self.merge(merged))
        return embedding

    def forward(self, features, adjacency):
        embedding = self.encode(features, adjacency)
        scores = self.regressor(embedding).squeeze(-1)
        return scores, embedding
