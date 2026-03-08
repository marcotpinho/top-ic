import torch.nn as nn
import torch


class PathEncoder(nn.Module):
    def __init__(self, input_dim=3, hidden_dim=64):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, batch_first=True, num_layers=2)

    def forward(self, x, lengths):
        packed = nn.utils.rnn.pack_padded_sequence(x, lengths.cpu(), batch_first=True, enforce_sorted=False)
        _, (h_n, _) = self.lstm(packed)
        ordered_h_n = h_n.index_select(1, packed.unsorted_indices)
        return ordered_h_n[-1]


class SimpleAggregation(nn.Module):
    """Simplified aggregation: just sum agent embeddings per instance."""
    def __init__(self, hidden_dim=64):
        super().__init__()
        self.hidden_dim = hidden_dim

    def forward(self, agents_embs, ids):
        """
        Simple aggregation by summing embeddings for each instance.

        Args:
            agents_embs: [num_agents, hidden_dim]
            ids: [num_agents] - instance ID for each agent

        Returns:
            pooled_outputs: [num_instances, hidden_dim]
        """
        unique_ids, inverse_indices = ids.unique(return_inverse=True)
        num_instances = len(unique_ids)

        # Sum embeddings for each instance
        summed = torch.zeros(num_instances, self.hidden_dim, device=agents_embs.device)
        summed.index_add_(0, inverse_indices, agents_embs)

        return summed


class PredictionHead(nn.Module):
    def __init__(self, hidden_dim=64):
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim * 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1)
        )

    def forward(self, x):
        return self.fc(x).squeeze(1)


class DistanceModelSimplified(nn.Module):
    """Simplified distance model without transformer - just LSTM + Sum + MLP."""
    def __init__(self, hidden_dim=128, device=None):
        super().__init__()
        self.path_encoder = PathEncoder(hidden_dim=hidden_dim)
        self.aggregation = SimpleAggregation(hidden_dim=hidden_dim)
        self.prediction_head = PredictionHead(hidden_dim=hidden_dim)
        self.device = device

    def forward(self, batch):
        points = batch['points'].to(self.device)
        lengths = batch['lengths'].to(self.device)
        instance_ids = batch['instance_ids'].to(self.device)

        # Encode paths
        path_embs = self.path_encoder(points, lengths)

        # Simple aggregation (sum)
        aggregated_embs = self.aggregation(path_embs, instance_ids)

        # Predict
        predictions = self.prediction_head(aggregated_embs)

        return predictions
