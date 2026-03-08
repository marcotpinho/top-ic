
# Cell 0
import numpy as np
import json
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

try:
    from src.db_utils import load_from_db
except ModuleNotFoundError:
    from db_utils import load_from_db

# Cell 1
class RankNetDataset(Dataset):
    def __init__(self, data_dir="data", split="train"):
        data_file = f"{data_dir}/distances_{split}_.json"
        print(f"Loading data from {data_file}...")

        self.split = split
        self.X, self.y, self.map_groups = load_from_db(data_file)

        with open(f"{data_dir}/speeds_stats.json", 'r') as f:
            stats = json.load(f)
            self.std_speed = stats["std_speed"]
            self.mean_speed = stats["mean_speed"]

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

class PairDataset(RankNetDataset):
    def __init__(self, same_map_only=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.same_map_only = same_map_only

    def __getitem__(self, i1):
        i1_x, i1_y = super().__getitem__(i1)

        if self.same_map_only:
            i2 = np.random.choice(self.map_groups[i1_x["map"]])
        else:
            i2 = np.random.randint(len(self))

        i2_x, i2_y = super().__getitem__(i2)

        speeds1, speeds2 = self.normalize_speeds(i1_x["speeds"], i2_x["speeds"])
        coords1 = self.normalize_coordinates(
            i1_x["coordinates"],
            i1_x["map_bounds"]["max_x"], i1_x["map_bounds"]["max_y"],
            i1_x["map_bounds"]["min_x"], i1_x["map_bounds"]["min_y"]
        )
        coords2 = self.normalize_coordinates(
            i2_x["coordinates"],
            i2_x["map_bounds"]["max_x"], i2_x["map_bounds"]["max_y"],
            i2_x["map_bounds"]["min_x"], i2_x["map_bounds"]["min_y"]
        )
        # ts1 = self.normalize_timestamps(i1_x["timestamps"])
        # ts2 = self.normalize_timestamps(i2_x["timestamps"])
        # coords1 = [np.concatenate([c, t[:, None]], axis=1) for c, t in zip(coords1, ts1)]
        # coords2 = [np.concatenate([c, t[:, None]], axis=1) for c, t in zip(coords2, ts2)]

        if i1_y > i2_y:
            label = 1
        elif i1_y < i2_y:
            label = -1
        else:
            label = 0

        return (coords1, speeds1), (coords2, speeds2), torch.tensor(label, dtype=torch.float32)

    def normalize_speeds(self, speeds1, speeds2):
        if self.std_speed > 0:
            return (speeds1 - self.mean_speed) / self.std_speed, (speeds2 - self.mean_speed) / self.std_speed
        return speeds1 - self.mean_speed, speeds2 - self.mean_speed

    def normalize_coordinates(self, coords, max_x, max_y, min_x, min_y):
        max_vals = np.array([max_x, max_y])
        min_vals = np.array([min_x, min_y])
        map_diag = np.linalg.norm(max_vals - min_vals)
        center = (max_vals + min_vals) / 2
        coords_normalized = []
        for c in coords:
            coords_normalized.append((c - center) / (map_diag + 1e-6))
        return coords_normalized

    def normalize_timestamps(self, timestamps: list) -> np.ndarray:
        times_flat = np.array([ts for times in timestamps for ts in times])
        t_max = times_flat.max()
        t_min = times_flat.min()
        times_normalized = []
        for ts in timestamps:
            times_normalized.append((ts - t_min) / (t_max - t_min + 1e-6))
        return times_normalized

class RankNetDataloader(DataLoader):
    def __init__(self, dataset, *args, **kwargs):
        super().__init__(dataset, collate_fn=self.collate_fn, *args, **kwargs)

    def collate_fn(self, batch):
        xs = []
        x_speeds = []
        x_len = []
        ids = []
        for id, x in enumerate(batch):
            coords, speeds = x
            xs.extend([torch.tensor(path, dtype=torch.float32) for path in coords])
            x_speeds.extend(speeds)
            x_len.extend([len(path) for path in coords])
            ids.extend([id] * len(coords))

        padded_x = nn.utils.rnn.pad_sequence(xs, batch_first=True)
        x_speeds = torch.tensor(x_speeds, dtype=torch.float32)
        x_len = torch.tensor(x_len, dtype=torch.long)
        ids = torch.tensor(ids, dtype=torch.long)

        return padded_x, x_speeds, x_len, ids

class PairDataloader(RankNetDataloader):
    def collate_fn(self, batch):
        x1, x2, labels = zip(*batch)
        padded_x1, speeds1, x1_len, ids1 = super().collate_fn(x1)
        padded_x2, speeds2, x2_len, ids2 = super().collate_fn(x2)
        labels = torch.stack(labels)
        return (padded_x1, speeds1, x1_len, ids1), (padded_x2, speeds2, x2_len, ids2), labels


# Cell 2
train_dataset = PairDataset(split="train")

# Cell 3
val_dataset = PairDataset(split="val")

# Cell 4
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
        # summed = self.att(encoded_x, x_ids)

        scores = self.rho(summed)

        return scores

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

def train_epoch(model, loader, criterion, optimizer, device):
    model.train()
    total_loss = 0
    for i, (x1, x2, labels) in enumerate(tqdm(loader)):
        padded_x1, speeds1, x1_len, x1_ids = x1
        padded_x1, speeds1, x1_ids = padded_x1.to(device), speeds1.to(device), x1_ids.to(device)
        x1_len = x1_len.cpu()

        padded_x2, speeds2, x2_len, x2_ids = x2
        padded_x2, speeds2, x2_ids = padded_x2.to(device), speeds2.to(device), x2_ids.to(device)
        x2_len = x2_len.cpu()

        labels = labels.to(device)

        optimizer.zero_grad()
        s1 = model(padded_x1, speeds1, x1_len, x1_ids)
        s2 = model(padded_x2, speeds2, x2_len, x2_ids)
        if i == 0:
            print(f"\n=== DIAGNOSTICS ===")
            print(f"s1: min={s1.min():.6f}, max={s1.max():.6f}, mean={s1.mean():.6f}, std={s1.std():.6f}")
            print(f"s2: min={s2.min():.6f}, max={s2.max():.6f}, mean={s2.mean():.6f}, std={s2.std():.6f}")
            print(f"s1-s2: min={(s1-s2).min():.6f}, max={(s1-s2).max():.6f}, mean={(s1-s2).mean():.6f}")
            print(f"Labels: {labels[:10]}")  # First 10 labels

        loss = criterion(s1, s2, labels)
        loss.backward()
        optimizer.step()

        if i == 0:
            # Check if gradients exist
            grad_norm = sum(p.grad.norm().item()**2 for p in model.parameters() if p.grad is not None)**0.5
            print(f"Gradient norm: {grad_norm:.6f}")

            # Check specific layer gradients
            print(f"LSTM grad norm: {model.phi.lstm.weight_ih_l0.grad.norm():.6f}")
            print(f"MLP final layer grad norm: {model.rho[-1].weight.grad.norm():.6f}")
            print("==================\n")

        total_loss += loss.item()
    return total_loss / len(loader)

def evaluate(model, loader, criterion, device):
    model.eval()
    total_loss = 0
    with torch.no_grad():
        for x1, x2, labels in tqdm(loader):
            padded_x1, speeds1, x1_len, x1_ids = x1
            padded_x1, speeds1, x1_ids = padded_x1.to(device), speeds1.to(device), x1_ids.to(device)

            padded_x2, speeds2, x2_len, x2_ids = x2
            padded_x2, speeds2, x2_ids = padded_x2.to(device), speeds2.to(device), x2_ids.to(device)

            labels = labels.to(device)

            s1 = model(padded_x1, speeds1, x1_len, x1_ids)
            s2 = model(padded_x2, speeds2, x2_len, x2_ids)

            loss = criterion(s1, s2, labels)
            total_loss += loss.item()
    return total_loss / len(loader)

def train(model, train_loader, val_loader, optimizer, device, criterion):
    losses = []
    patience = 15
    best_val_loss = float("inf")

    for epoch in range(100):
        train_loss = train_epoch(model, train_loader, criterion, optimizer, device)
        val_loss = evaluate(model, val_loader, criterion, device)
        losses.append((train_loss, val_loss))

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience = 15
            model_path = "models/ranknet_model_ptpq.pth"
            torch.save({
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'losses': losses,
            }, model_path)
            print(f"Model saved to {model_path}")
        else:
            patience -= 1
            if patience == 0:
                print("Early stopping triggered.")
                break
        print(f"Epoch {epoch+1}: Train Loss = {train_loss}, Val Loss = {val_loss}")
    return losses

def init_weights(m):
    if isinstance(m, nn.Linear):
        nn.init.xavier_uniform_(m.weight, gain=1.0)
        if m.bias is not None:
            nn.init.constant_(m.bias, 0.0)
    elif isinstance(m, nn.LSTM):
        for name, param in m.named_parameters():
            if 'weight_ih' in name:
                nn.init.xavier_uniform_(param)
            elif 'weight_hh' in name:
                nn.init.orthogonal_(param)
            elif 'bias' in name:
                nn.init.constant_(param, 0.0)

# Cell 5
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Using device:", device)

model = RankNet(input_dim=2, hidden_dim=64).to(device)
model.apply(init_weights)
train_loader = PairDataloader(train_dataset, batch_size=32, shuffle=True, num_workers=4)
val_loader = PairDataloader(val_dataset, batch_size=32, shuffle=False, num_workers=4)
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

loss_fn = torch.nn.MarginRankingLoss(margin=0.1)
# loss_fn = torch.nn.BCEWithLogitsLoss()
def ranknet_loss(s1, s2, t, loss_fn=loss_fn):
    non_tie = (t != 0)
    s1_masked = s1.squeeze()[non_tie]
    s2_masked = s2.squeeze()[non_tie]
    t_masked = t[non_tie]
    return loss_fn(s1_masked, s2_masked, t_masked)


# Cell 6
losses = train(model, train_loader, val_loader, optimizer, device, ranknet_loss)

# Save the trained model
model_path = "models/ranknet_model_ptpq.pth"
torch.save({
    'model_state_dict': model.state_dict(),
    'optimizer_state_dict': optimizer.state_dict(),
    'losses': losses,
}, model_path)
print(f"Model saved to {model_path}")

# Cell 7
labels_count = {0: 0, 0.5: 0, 1: 0}
for i in range(len(train_dataset)):
    _, _, label = train_dataset[i]
    if label < 0.3:
        labels_count[0] += 1
    elif label > 0.7:
        labels_count[1] += 1
    else:
        labels_count[0.5] += 1
print("Label distribution in training data:")
print(labels_count)

