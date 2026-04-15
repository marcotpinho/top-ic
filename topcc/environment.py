"""Environment representations for TOP-CC problem instances."""

import numpy as np
from pathlib import Path
from scipy.spatial.distance import cdist
from typing import Tuple


class Map2D:
    """2D Euclidean environment with positions, rewards, and distance matrix."""

    def __init__(self, rpositions: np.ndarray, rvalues: np.ndarray):
        self.rpositions = rpositions
        self.rvalues = rvalues
        self.distmx = cdist(rpositions, rpositions, metric="euclidean")


def load_problem_instance(map_file_path: str) -> Tuple[
    int, int, list[float], list[float], np.ndarray, np.ndarray
]:
    """Parse a map file into problem instance data.

    Returns:
        (num_rewards, num_agents, budget, speeds, rpositions, rvalues)
    """
    map_path = Path(map_file_path)
    if not map_path.exists():
        raise FileNotFoundError(f"Map file not found: {map_file_path}")

    try:
        with open(map_path, "r") as f:
            lines = f.readlines()

        num_rewards = int(float(lines[0].split()[1]))
        num_agents = int(lines[1].split()[1])
        default_budget = float(lines[2].split()[1])

        budget = [default_budget] * num_agents
        default_speeds = [1.0] * num_agents

        reward_data = []
        for line in lines[3:]:
            parts = line.strip().split()
            if len(parts) >= 3:
                x, y, value = float(parts[0]), float(parts[1]), float(parts[2])
                reward_data.append([x, y, value])

        if not reward_data:
            raise ValueError("No reward data found in map file")

        reward_array = np.array(reward_data)
        rpositions = np.vstack([reward_array[1:, :2], reward_array[0:1, :2]])
        rvalues = np.concatenate([reward_array[1:, 2], reward_array[0:1, 2]])

        return num_rewards, num_agents, budget, default_speeds, rpositions, rvalues

    except (IndexError, ValueError) as e:
        raise ValueError(f"Invalid map file format: {e}")
