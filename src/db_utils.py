# src/db_utils.py
from collections import defaultdict
import json
import numpy as np
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import CONFIG


MAX_FILE_SIZE = 25 * 1024 * 1024 * 1024  # 25 GB in bytes


def calculate_entry_hash(paths: list[np.ndarray], speeds: np.ndarray, rpositions: np.ndarray) -> str:
    hash_obj = hashlib.sha256()
    
    for path in paths:
        hash_obj.update(path.astype(int).tobytes())
    
    hash_obj.update(speeds.astype(float).tobytes())
    hash_obj.update(rpositions.astype(float).tobytes())
    
    return hash_obj.hexdigest()


def load_db(filepath: str = None) -> List[Dict[str, Any]]:
    if filepath is None:
        filepath = CONFIG.db_path
    
    if not Path(filepath).exists():
        return []
    
    try:
        data = []
        with open(filepath, "r") as f:
            for line in f:
                if line.strip():  # Skip empty lines
                    data.append(json.loads(line))
        return data
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading database: {e}")
        return []


def append_to_db(entry: Dict[str, Any], filepath: str = None) -> None:
    if filepath is None:
        filepath = CONFIG.db_path
    
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(filepath, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except IOError as e:
        print(f"Error appending to database: {e}")


def save_to_db(
    paths: list[np.ndarray],
    speeds: np.ndarray,
    rpositions: np.ndarray,
    max_distance: float,
    filepath: str = None
) -> None:
    if filepath is None:
        filepath = CONFIG.db_path
    
    if Path(filepath).exists():
        current_size = Path(filepath).stat().st_size
        if current_size >= MAX_FILE_SIZE:
            print("Database size limit reached. Skipping save.")
            return
    
    try:
        if not paths or len(paths) == 0:
            print("Empty paths provided. Skipping save.")
            return
        if any(p is None or len(p) == 0 for p in paths):
            print("One or more paths are None or empty. Skipping save.")
            return

        entry_hash = calculate_entry_hash(paths, speeds, rpositions)
        
        existing_hashes = set()
        if Path(filepath).exists():
            with open(filepath, "r") as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        existing_hashes.add(entry.get("entry_hash"))
        
        if entry_hash in existing_hashes:
            return
        
        timestamps, coordinates = calculate_timestamps_and_coordinates(paths, rpositions, speeds)
        
        data = load_db(filepath)
        next_id = len(data) + 1
        
        entry = {
            "id": next_id,
            "max_distance": float(max_distance),
            "paths": [p.astype(int).tolist() for p in paths],
            "speeds": speeds.astype(float).tolist(),
            "entry_hash": entry_hash,
            "timestamps": timestamps,
            "coordinates": coordinates,
            "map": CONFIG.map_file,
            "map_bounds": {
                "min_x": float(np.min(rpositions[:, 0])),
                "max_x": float(np.max(rpositions[:, 0])),
                "min_y": float(np.min(rpositions[:, 1])),
                "max_y": float(np.max(rpositions[:, 1])),
            }
        }
        
        append_to_db(entry, filepath)

    except Exception as e:
        print(f"Error saving calculation: {e}")


def load_from_db(
    filepath: str = None,
    limit: int = None,
):
    if filepath is None:
        filepath = CONFIG.db_path
    
    data = json.load(open(filepath, "r"))
    
    if not data:
        return
    
    try:
        X = []
        y = []
        map_groups = defaultdict(list)

        for i, entry in enumerate(data):
            if limit is not None and i >= limit:
                break

            x_i = {
                "max_distance": entry["max_distance"],
                "paths": [np.array(path) for path in entry["paths"]],
                "speeds": np.array(entry["speeds"]),
                "timestamps": [np.array(ts) for ts in entry["timestamps"]],
                "coordinates": [np.array(coord) for coord in entry["coordinates"]],
                "map_bounds": entry["map_bounds"],
                "map": entry["map"]
            }
            y_i = entry["max_distance"]
            X.append(x_i)
            y.append(y_i)
            map_groups[entry["map"]].append(i)

        return X, y, map_groups

    except Exception as e:
        print(f"Error loading data from database: {e}")
        return []


def count_db_entries(filepath: str = None) -> int:
    if filepath is None:
        filepath = CONFIG.db_path
    
    data = load_db(filepath)
    return len(data)


def calculate_coordinates(paths, rpositions):
    coordinates = []
    for path in paths:
        path_coordinates = rpositions[path].tolist()
        coordinates.append(path_coordinates)
    return coordinates


def calculate_timestamps(coordinates, speeds):
    timestamps = []
    for path_coords, speed in zip(coordinates, speeds):
        dist = np.linalg.norm(np.diff(path_coords, axis=0), axis=1)
        time = dist / speed
        timestamps.append(np.insert(np.cumsum(time), 0, 0).tolist())
    return timestamps


def calculate_timestamps_and_coordinates(paths, rpositions, speeds):
    coordinates = calculate_coordinates(paths, rpositions)
    timestamps = calculate_timestamps(coordinates, speeds)
    return timestamps, coordinates


if __name__ == "__main__":
    # import os
    # all_data = []
    # for file in os.listdir("data/"):
    #     if file.endswith("_distances_train.json"):
    #         db_path = os.path.join("data/", file)
    #         all_data.extend(load_db(db_path))
    # np.random.shuffle(all_data)
    # train_data = all_data[:int(0.8 * len(all_data))]
    # test_data = all_data[int(0.8 * len(all_data)):]
    # train_data = train_data[:int(0.8 * len(train_data))]
    # val_data = train_data[int(0.8 * len(train_data)):]
    # print(f"Total entries: {len(all_data)}")
    # print(f"Train entries: {len(train_data)}")
    # print(f"Test entries: {len(test_data)}")
    # print(f"Validation entries: {len(val_data)}")

    # with open("data/distances_train.json", 'w') as f:
    #     json.dump(train_data, f)
    # with open("data/distances_test.json", 'w') as f:
    #     json.dump(test_data, f)
    # with open("data/distances_val.json", 'w') as f:
    #     json.dump(val_data, f)

    # def add_map_bounds(dataset, output_file):
    #     data = json.load(open(dataset, 'r'))
    #     map_buffer = {}
    #     for entry in data:
    #         map_file = entry['map']
    #         if map_file in map_buffer:
    #             entry['map_bounds'] = map_buffer[map_file]
    #         else:
    #             with open(map_file, 'r') as f:
    #                 map_data = f.readlines()
    #                 points = map_data[3:]
    #                 xs = [float(points[i].split()[0]) for i in range(len(points))]
    #                 ys = [float(points[i].split()[1]) for i in range(len(points))]
    #                 min_x, max_x = min(xs), max(xs)
    #                 min_y, max_y = min(ys), max(ys)
    #             entry['map_bounds'] = {
    #                 'min_x': float(min_x),
    #                 'max_x': float(max_x),
    #                 'min_y': float(min_y),
    #                 'max_y': float(max_y)
    #             }
    #             map_buffer[map_file] = entry['map_bounds']
    #     with open(output_file, 'w') as f:
    #         json.dump(data, f)
    # add_map_bounds("data/distances_test.json", "data/distances_test_.json")
    # add_map_bounds("data/distances_train.json", "data/distances_train_.json")
    # add_map_bounds("Aata/distances_val.json", "data/distances_val_.json")
    data = json.load(open("data/distances_train_.json", 'r'))
    speeds = []
    for entry in data:
        speeds.extend(entry['speeds'])
    with open("data/speeds_stats.json", 'w') as f:
        json.dump({
            'min_speed': float(np.min(speeds)),
            'max_speed': float(np.max(speeds)),
            'mean_speed': float(np.mean(speeds)),
            'std_speed': float(np.std(speeds))
        }, f)
                     
