"""
RankNet model definitions (extracted from ranknet_train.py)
"""
import torch
import torch.nn as nn


class Encoder(nn.Module):
    def __init__(self, input_dim, hidden_dim):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, batch_first=True, num_layers=2)

    def forward(self, padded_x, lengths):
        packed_x = nn.utils.rnn.pack_padded_sequence(padded_x,
                                                     lengths=lengths,
                                                     batch_first=True,
                                                     enforce_sorted=False)
        _, (h_n, _) = self.lstm(packed_x)
        ordered_h_n = h_n.index_select(1, packed_x.unsorted_indices)
        return ordered_h_n[-1]


class InteractionModule(nn.Module):
    def __init__(self, hidden_dim=64, nhead=4, nlayers=2):
        super().__init__()
        encoder_layer = nn.TransformerEncoderLayer(d_model=hidden_dim, nhead=nhead, batch_first=True)
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=nlayers)
        self.hidden_dim = hidden_dim

    def forward(self, agents_embs, ids):
        unique_ids, idx = ids.unique(return_inverse=True)
        num_groups = unique_ids.shape[0]
        group_sizes = torch.bincount(idx)
        max_group_size = group_sizes.max()

        group_positions = torch.zeros_like(idx, device=agents_embs.device)
        group_positions[torch.argsort(idx)] = torch.cat([torch.arange(size, device=agents_embs.device) for size in group_sizes])

        flat_indices = idx * max_group_size + group_positions
        group_embs = torch.zeros(num_groups * max_group_size, self.hidden_dim, device=agents_embs.device)
        padding_mask = torch.ones(num_groups * max_group_size, dtype=torch.bool, device=agents_embs.device)

        group_embs.scatter_(0, flat_indices.unsqueeze(1).expand_as(agents_embs), agents_embs)
        padding_mask.scatter_(0, flat_indices, False)

        group_embs = group_embs.view(num_groups, max_group_size, self.hidden_dim)
        padding_mask = padding_mask.view(num_groups, max_group_size)

        transformer_output = self.transformer(group_embs, src_key_padding_mask=padding_mask)

        masked_output = transformer_output * (~padding_mask).unsqueeze(-1).float()
        valid_lengths = (~padding_mask).sum(dim=1, keepdim=True).float()
        pooled_outputs = masked_output.sum(dim=1) / torch.clamp(valid_lengths, min=1.0)
        return pooled_outputs


class RankNet(nn.Module):
    def __init__(self, input_dim=3, hidden_dim=64):
        super().__init__()
        self.phi = Encoder(input_dim=input_dim, hidden_dim=hidden_dim)
        self.agent_emb = nn.Sequential(
            nn.Linear(hidden_dim + 1, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim)
        )
        self.att = InteractionModule(hidden_dim=hidden_dim)
        self.rho = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim * 2),
            nn.ReLU(),
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )

    def forward(self, padded_x, speeds, x_len, x_ids):
        encoded_x = self.phi(padded_x, x_len)
        emb = torch.cat([encoded_x, speeds.unsqueeze(1)], dim=1)
        encoded_x = self.agent_emb(emb)

        unique_ids, inverse_indices = torch.unique(x_ids, return_inverse=True)
        num_unique = len(unique_ids)

        summed = torch.zeros(num_unique, encoded_x.size(1), device=encoded_x.device)
        summed.index_add_(0, inverse_indices, encoded_x)
        # summed = self.att(encoded_x, x_ids)  # Transformer commented out - uses SUM

        scores = self.rho(summed)

        return scores
