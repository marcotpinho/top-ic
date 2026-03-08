import numpy as np
import torch
import torch.nn as nn
from typing import List

from src.config import CONFIG
from src.entities import Map
from src.entities.DistanceModelSimplified import DistanceModelSimplified

EPSILON = 1e-8


def load_model(model_path: str = "checkpoints/model.pth"):
    if CONFIG.model is None:
        CONFIG.model_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        CONFIG.model = DistanceModelSimplified(device=CONFIG.model_device).to(CONFIG.model_device)
        CONFIG.model.load_state_dict(torch.load(model_path, map_location=CONFIG.model_device))
        print(f"Simplified Model loaded on {CONFIG.model_device}")

    return CONFIG.model


def predict_max_distance(coords, timestamps) -> float:
    """Single instance prediction (backward compatibility)."""
    results = predict_max_distance_batch([coords], [timestamps])
    return results[0]


def predict_max_distance_batch(
    coords_batch: List[List[np.ndarray]],
    timestamps_batch: List[List[np.ndarray]],
    mapp: Map
) -> List[float]:
    model = load_model()

    if len(coords_batch) == 0:
        return []

    all_coords = []
    all_timestamps = []
    instance_ids = []
    instance_map_diags = []

    for instance_id, (coords, timestamps) in enumerate(zip(coords_batch, timestamps_batch)):
        if len(coords) == 0:
            instance_map_diags.append(1.0)
            continue

        all_coords.extend(coords)
        all_timestamps.extend(timestamps)
        instance_ids.extend([instance_id] * len(coords))

    if len(all_coords) == 0:
        return [0.0] * len(coords_batch)

    batch_data = transform_input_batch(all_coords, all_timestamps, instance_ids, mapp.diag, mapp.center)

    with torch.no_grad():
        predictions = model(batch_data)

    results = []
    for pred in predictions:
        denormalized = pred.item() * mapp.diag
        results.append(denormalized)

    return results


def transform_input_batch(coords, timestamps, instance_ids, map_diag, map_center) -> dict:
    coords_normalized, global_map_diag = normalize_coordinates_batch(coords, map_diag, map_center)
    coords_tensors = [torch.tensor(c, dtype=torch.float32) for c in coords_normalized]

    times_normalized, _, _ = normalize_timestamps_batch(timestamps)
    times_tensors = [torch.tensor(ts, dtype=torch.float32).unsqueeze(-1) for ts in times_normalized]

    points_normalized = [torch.hstack((c, ts)) for c, ts in zip(coords_tensors, times_tensors)]

    lengths = torch.tensor([len(path) for path in points_normalized])
    instance_ids_tensor = torch.tensor(instance_ids)

    padded = nn.utils.rnn.pad_sequence(points_normalized, batch_first=True)

    return {
        "points": padded.to(CONFIG.model_device),
        "lengths": lengths.to(CONFIG.model_device),
        "instance_ids": instance_ids_tensor.to(CONFIG.model_device),
        "map_diag": torch.tensor(global_map_diag, dtype=torch.float32).to(CONFIG.model_device)
    }


def normalize_coordinates_batch(coordinates: list, map_diag: float, map_center: np.ndarray) -> tuple[list, float]:
    if not coordinates or len(coordinates) == 0:
        return [], 1.0

    coords_normalized = []
    for coords in coordinates:
        normalized = (coords - map_center) / map_diag
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
