import torch.nn as nn
import torch


class Encoder(nn.Module):
    """LSTM encoder for agent paths (same as ranknet_train.py)."""
    def __init__(self, input_dim, hidden_dim):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, batch_first=True, num_layers=2)

    def forward(self, padded_x, lengths):
        packed_x = nn.utils.rnn.pack_padded_sequence(padded_x,
                                                     lengths=lengths.cpu(),
                                                     batch_first=True,
                                                     enforce_sorted=False)
        _, (h_n, _) = self.lstm(packed_x)
        ordered_h_n = h_n.index_select(1, packed_x.unsorted_indices)
        return ordered_h_n[-1]


class DistanceModelCorrected(nn.Module):
    """
    Corrected DistanceModel matching the RankNet architecture used in training.
    - LSTM encoder (phi)
    - Agent embedding with speeds (agent_emb)
    - Simple sum aggregation (NO transformer - it was commented out in training)
    - Prediction head (rho)
    - Uses input_dim=2 (x, y only, NO timestamps)
    """
    def __init__(self, input_dim=2, hidden_dim=64, device=None):
        super().__init__()
        # Encoder (same as RankNet.phi)
        self.phi = Encoder(input_dim=input_dim, hidden_dim=hidden_dim)

        # Agent embedding (same as RankNet.agent_emb)
        # Takes encoded path + speed → hidden_dim
        self.agent_emb = nn.Sequential(
            nn.Linear(hidden_dim + 1, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim)
        )

        # Prediction head (same as RankNet.rho)
        self.rho = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim * 2),
            nn.ReLU(),
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )

        self.device = device

    def forward(self, batch):
        """
        Forward pass matching RankNet training.

        Args:
            batch: dict with keys 'points', 'lengths', 'instance_ids', 'speeds'
        """
        points = batch['points'].to(self.device)
        lengths = batch['lengths'].to(self.device)
        instance_ids = batch['instance_ids'].to(self.device)
        speeds = batch.get('speeds', torch.ones(len(points), device=self.device))  # Default to 1.0 if not provided

        # Encode paths
        encoded_x = self.phi(points, lengths)

        # Concatenate with speeds and pass through agent_emb
        emb = torch.cat([encoded_x, speeds.unsqueeze(1)], dim=1)
        encoded_x = self.agent_emb(emb)

        # Simple sum aggregation by instance_id (NO transformer - was commented out in training)
        unique_ids, inverse_indices = torch.unique(instance_ids, return_inverse=True)
        num_unique = len(unique_ids)

        summed = torch.zeros(num_unique, encoded_x.size(1), device=encoded_x.device)
        summed.index_add_(0, inverse_indices, encoded_x)

        # Predict
        scores = self.rho(summed)

        return scores
