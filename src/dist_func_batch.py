import numpy as np
import torch
import torch.nn as nn
from typing import List
import json
from pathlib import Path

from src.config import CONFIG
from src.entities import Map

# Import RankNet model from model definitions (not training script)
from src.ranknet_model import RankNet

EPSILON = 1e-6  # Match training epsilon

# Load speed normalization statistics (computed during training)
_SPEED_STATS_PATH = Path("data/speeds_stats.json")
_SPEED_STATS = None

def _load_speed_stats():
    global _SPEED_STATS
    if _SPEED_STATS is None:
        try:
            with open(_SPEED_STATS_PATH, 'r') as f:
                _SPEED_STATS = json.load(f)
        except:
            # Default values if file not found
            _SPEED_STATS = {"mean_speed": 2.016, "std_speed": 0.553}
    return _SPEED_STATS


def load_model(model_path: str = "models/ranknet_model_ptpq.pth"):
    if CONFIG.model is None:
        CONFIG.model_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        CONFIG.model = RankNet(input_dim=2, hidden_dim=64).to(CONFIG.model_device)

        try:
            checkpoint = torch.load(model_path, map_location=CONFIG.model_device)
            if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
                state_dict = checkpoint['model_state_dict']
            else:
                state_dict = checkpoint
            CONFIG.model.load_state_dict(state_dict, strict=True)
            print(f"RankNet Model (hidden_dim=64) loaded from {model_path} on {CONFIG.model_device}")
        except Exception as e:
            print(f"ERROR loading RankNet Model: {e}")
            raise

    return CONFIG.model


def predict_max_distance(coords, timestamps) -> float:
    """Single instance prediction (backward compatibility)."""
    results = predict_max_distance_batch([coords], [timestamps])
    return results[0]


def predict_max_distance_batch(
    coords_batch: List[List[np.ndarray]],
    timestamps_batch: List[List[np.ndarray]],
    speeds: np.ndarray,
    mapp: Map
) -> List[float]:
    model = load_model()
    
    if len(coords_batch) == 0:
        return []

    all_coords = []
    all_timestamps = []
    instance_ids = []
    all_speeds = []
    instance_map_diags = []

    for instance_id, (coords, timestamps) in enumerate(zip(coords_batch, timestamps_batch)):
        if len(coords) == 0:
            instance_map_diags.append(1.0)
            continue

        all_coords.extend(coords)
        all_timestamps.extend(timestamps)
        instance_ids.extend([instance_id] * len(coords))
        # Each instance has len(coords) agents, each with their own speed
        all_speeds.extend(speeds[:len(coords)])

    if len(all_coords) == 0:
        return [0.0] * len(coords_batch)

    batch_data = transform_input_batch(all_coords, all_timestamps, instance_ids, all_speeds, mapp.diag, mapp.center)
    
    with torch.no_grad():
        predictions = model(
            batch_data["points"],
            batch_data["speeds"],
            batch_data["lengths"],
            batch_data["instance_ids"]
        )

    results = []
    for pred in predictions:
        denormalized = pred.item() * mapp.diag
        results.append(denormalized)
    
    return results


def transform_input_batch(coords, timestamps, instance_ids, speeds, map_diag, map_center) -> dict:
    # Normalize coordinates (vectorized, matching ranknet_train.py)
    coords_normalized, global_map_diag = normalize_coordinates_batch(coords, map_diag, map_center)

    # RankNet was trained with 2D coordinates only (x, y), NO timestamps
    # Vectorized tensor creation
    points_normalized = [torch.tensor(c, dtype=torch.float32) for c in coords_normalized]

    # Normalize speeds using training statistics (vectorized)
    speeds_normalized = normalize_speeds_batch(np.array(speeds))

    # Create tensors (batch operations)
    lengths = torch.tensor([len(path) for path in points_normalized], dtype=torch.long)
    instance_ids_tensor = torch.tensor(instance_ids, dtype=torch.long)
    speeds_tensor = torch.tensor(speeds_normalized, dtype=torch.float32)

    # Pad sequences
    padded = nn.utils.rnn.pad_sequence(points_normalized, batch_first=True)

    return {
        "points": padded.to(CONFIG.model_device),
        "lengths": lengths,  # Keep on CPU for pack_padded_sequence
        "instance_ids": instance_ids_tensor.to(CONFIG.model_device),
        "speeds": speeds_tensor.to(CONFIG.model_device),
        "map_diag": torch.tensor(global_map_diag, dtype=torch.float32).to(CONFIG.model_device)
    }


def normalize_speeds_batch(speeds: np.ndarray) -> np.ndarray:
    """Normalize speeds using training statistics (vectorized)."""
    stats = _load_speed_stats()
    mean_speed = stats["mean_speed"]
    std_speed = stats["std_speed"]

    if std_speed > 0:
        return (speeds - mean_speed) / std_speed
    return speeds - mean_speed


def normalize_coordinates_batch(coordinates: list, map_diag: float, map_center: np.ndarray) -> tuple[list, float]:
    if not coordinates or len(coordinates) == 0:
        return [], 1.0

    # Vectorized normalization matching ranknet_train.py
    coords_normalized = []
    for coords in coordinates:
        normalized = (coords - map_center) / (map_diag + EPSILON)
        coords_normalized.append(normalized)

    return coords_normalized, map_diag


def normalize_timestamps_batch(timestamps: list) -> tuple[list, float, float]:
    if not timestamps or len(timestamps) == 0:
        return [], 0.0, 1.0
    
    times_flat = np.array([ts for times in timestamps for ts in times])
    t_max = times_flat.max()
    t_min = times_flat.min()
    time_range = t_max - t_min + EPSILON
    
    times_normalized = []
    for ts in timestamps:
        normalized = (ts - t_min) / time_range
        times_normalized.append(normalized)
    
    return times_normalized, t_max, t_min


def transform_input(coords, timestamps) -> dict:
    return transform_input_batch(coords, timestamps, [0] * len(coords))


def normalize_coordinates(coordinates: list) -> tuple[list, float]:
    return normalize_coordinates_batch(coordinates)


def normalize_timestamps(timestamps: list) -> tuple[list, float, float]:
    return normalize_timestamps_batch(timestamps)
