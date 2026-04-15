"""RankNet model definitions for surrogate distance prediction."""

import torch
import torch.nn as nn


class Encoder(nn.Module):
    def __init__(self, input_dim, hidden_dim):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, batch_first=True, num_layers=2)

    def forward(self, padded_x, lengths):
        packed_x = nn.utils.rnn.pack_padded_sequence(
            padded_x, lengths=lengths, batch_first=True, enforce_sorted=False
        )
        _, (h_n, _) = self.lstm(packed_x)
        ordered_h_n = h_n.index_select(1, packed_x.unsorted_indices)
        return ordered_h_n[-1]


class RankNet(nn.Module):
    def __init__(self, input_dim=2, hidden_dim=64):
        super().__init__()
        self.phi = Encoder(input_dim=input_dim, hidden_dim=hidden_dim)
        self.agent_emb = nn.Sequential(
            nn.Linear(hidden_dim + 1, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
        )
        self.rho = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim * 2),
            nn.ReLU(),
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, padded_x, speeds, x_len, x_ids):
        encoded_x = self.phi(padded_x, x_len)
        emb = torch.cat([encoded_x, speeds.unsqueeze(1)], dim=1)
        encoded_x = self.agent_emb(emb)

        unique_ids, inverse_indices = torch.unique(x_ids, return_inverse=True)
        num_unique = len(unique_ids)

        summed = torch.zeros(num_unique, encoded_x.size(1), device=encoded_x.device)
        summed.index_add_(0, inverse_indices, encoded_x)

        scores = self.rho(summed)
        return scores
