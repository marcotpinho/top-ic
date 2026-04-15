"""Batch distance prediction using the RankNet surrogate model."""

import numpy as np
import torch
import torch.nn as nn
from typing import List
import json
from pathlib import Path

from surrogate.ranknet import RankNet

EPSILON = 1e-6
_SPEED_STATS_PATH = Path("data/speeds_stats.json")
_SPEED_STATS = None
_MODEL = None
_DEVICE = None


def _load_speed_stats():
    global _SPEED_STATS
    if _SPEED_STATS is None:
        try:
            with open(_SPEED_STATS_PATH, "r") as f:
                _SPEED_STATS = json.load(f)
        except Exception:
            _SPEED_STATS = {"mean_speed": 2.016, "std_speed": 0.553}
    return _SPEED_STATS


def load_model(model_path: str = "models/ranknet_model_ptpq.pth"):
    global _MODEL, _DEVICE
    if _MODEL is None:
        _DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        _MODEL = RankNet(input_dim=2, hidden_dim=64).to(_DEVICE)
        checkpoint = torch.load(model_path, map_location=_DEVICE)
        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
            state_dict = checkpoint["model_state_dict"]
        else:
            state_dict = checkpoint
        _MODEL.load_state_dict(state_dict, strict=True)
        print(f"RankNet loaded from {model_path} on {_DEVICE}")
    return _MODEL


def predict_max_distance_batch(
    coords_batch: List[List[np.ndarray]],
    speeds: np.ndarray,
    map_diag: float,
    map_center: np.ndarray,
) -> List[float]:
    model = load_model()

    if len(coords_batch) == 0:
        return []

    all_coords = []
    instance_ids = []
    all_speeds = []

    for instance_id, coords in enumerate(coords_batch):
        if len(coords) == 0:
            continue
        all_coords.extend(coords)
        instance_ids.extend([instance_id] * len(coords))
        all_speeds.extend(speeds[: len(coords)])

    if len(all_coords) == 0:
        return [0.0] * len(coords_batch)

    # Normalize coordinates
    coords_normalized = [(c - map_center) / (map_diag + EPSILON) for c in all_coords]
    points = [torch.tensor(c, dtype=torch.float32) for c in coords_normalized]

    # Normalize speeds
    stats = _load_speed_stats()
    speeds_arr = np.array(all_speeds)
    if stats["std_speed"] > 0:
        speeds_norm = (speeds_arr - stats["mean_speed"]) / stats["std_speed"]
    else:
        speeds_norm = speeds_arr - stats["mean_speed"]

    lengths = torch.tensor([len(p) for p in points], dtype=torch.long)
    ids_tensor = torch.tensor(instance_ids, dtype=torch.long).to(_DEVICE)
    speeds_tensor = torch.tensor(speeds_norm, dtype=torch.float32).to(_DEVICE)
    padded = nn.utils.rnn.pad_sequence(points, batch_first=True).to(_DEVICE)

    with torch.no_grad():
        predictions = model(padded, speeds_tensor, lengths, ids_tensor)

    return [pred.item() * map_diag for pred in predictions]
