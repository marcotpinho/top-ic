import numpy as np
from numba import njit
from typing import List

from src.db_utils import save_to_db
from src.dist_func_batch import predict_max_distance_batch
from src.entities.Map import Map
from src.entities.Solution import Solution
from utils import calculate_rssi


class Evaluator:
    def __init__(self, map: Map = None, predict_distances: bool = False, should_save_to_db: bool = False):
        self.map = map
        self.predict_distances = predict_distances
        self.should_save_to_db = should_save_to_db

    def evaluate(self, solutions: List[Solution] | Solution) -> None:
        if not isinstance(solutions, list):
            solutions = [solutions]
        if len(solutions) == 0:
            return

        max_distances = []
        all_coordinates = []
        all_timestamps = []
        solution_results = []
        
        speeds = np.array(Solution.speeds)
        
        for solution in solutions:
            paths = solution.get_solution_paths()
            paths_flat = np.concatenate(paths)

            total_reward = maximize_reward(paths_flat, self.map.rvalues)

            max_len = get_paths_max_length(paths, self.map.distmx)

            coordinates = [self.map.rpositions[path] for path in paths]
            all_coordinates.append(coordinates)

            if not self.predict_distances:
                # Only calculate timestamps when using exact RSSI (surrogate doesn't need them)
                interesting_times, timestamps = get_time_to_rewards(paths, speeds, self.map.distmx)
                all_timestamps.append(timestamps)

                interpolated_positions = self.interpolate_positions(paths, speeds, interesting_times)
                max_distance = calculate_max_distance(interpolated_positions)
                max_distances.append(max_distance)

            # Store partial results
            solution_results.append({
                'total_reward': total_reward,
                'max_len': max_len,
                'paths': paths
            })
        
        if self.predict_distances:
            # RankNet model doesn't use timestamps, pass list of empty lists (one per solution)
            empty_timestamps = [[] for _ in all_coordinates]
            max_distances = predict_max_distance_batch(all_coordinates, empty_timestamps, speeds, self.map)

        for i, (max_distance, result) in enumerate(zip(max_distances, solution_results)):
            min_rssi = calculate_rssi(max_distance, noise=False)
            
            # if self.should_save_to_db and np.random.random() < 0.05:
            #     save_to_db(result['paths'], speeds, self.map.rpositions, max_distance)

            solutions[i].score = (result['total_reward'], min_rssi, -result['max_len'])

    def interpolate_positions(
        self,
        paths: list[np.ndarray],
        speeds: np.ndarray, # shape (k,)
        interesting_times: np.ndarray
    ) -> np.ndarray:
        num_paths = len(paths)
        num_times = len(interesting_times)
        interpolated_positions = np.zeros((num_paths, num_times, 2))
        
        for i in range(num_paths):
            path = paths[i]
            speed = speeds[i]

            if len(path) <= 1:
                continue
                
            time_to_rewards = np.zeros(len(path) - 1)
            cumulative_dist = 0.0
            for j in range(len(path) - 1):
                cumulative_dist += self.map.distmx[path[j], path[j + 1]]
                time_to_rewards[j] = cumulative_dist / speed
            
            x_positions = np.zeros(len(path) - 1)
            y_positions = np.zeros(len(path) - 1)
            for j in range(len(path) - 1):
                x_positions[j] = self.map.rpositions[path[j + 1], 0]
                y_positions[j] = self.map.rpositions[path[j + 1], 1]

            # Interpolate for each interesting time
            for t in range(num_times):
                if len(time_to_rewards) > 0:
                    interpolated_positions[i, t, 0] = np.interp(interesting_times[t], time_to_rewards, x_positions)
                    interpolated_positions[i, t, 1] = np.interp(interesting_times[t], time_to_rewards, y_positions)
        
        return interpolated_positions


@njit(cache=True, fastmath=True)
def get_paths_max_length(paths_array: np.ndarray, distmx: np.ndarray) -> float:
    max_distance = 0.0
    
    for i in range(len(paths_array)):
        path = paths_array[i]
        distances = 0.0
        for j in range(len(path) - 1):
            distances += distmx[path[j], path[j + 1]]
        if distances > max_distance:
            max_distance = distances
            
    return max_distance


@njit(cache=True, fastmath=True)
def get_time_to_rewards(
    paths: list[np.ndarray],
    speeds: np.ndarray, # shape (k,)
    distmx: np.ndarray # shape (n, n)
) -> tuple[np.ndarray, list[list[float]]]:
    all_times = []
    timestamps = []
    
    for i in range(len(paths)):
        path = paths[i]
        speed = speeds[i]
        path_times = [0.0]  # Start with time 0.0
        
        cumulative_dist = 0.0
        for j in range(len(path) - 1):
            cumulative_dist += distmx[path[j], path[j + 1]]
            ts = cumulative_dist / speed
            path_times.append(ts)
            all_times.append(ts)
        
        timestamps.append(path_times)

    if len(all_times) == 0:
        return np.array([0.0]), timestamps
    
    times_array = np.array(all_times)
    return np.unique(times_array), timestamps


@njit(cache=True, fastmath=True)
def calculate_max_distance(interpolated_positions: np.ndarray) -> float:
    if len(interpolated_positions) <= 1:
        return 0.0
    
    k, n, _ = interpolated_positions.shape
    max_distance = 0.0
    
    for i in range(k):
        for j in range(i + 1, k):
            for t in range(n):
                pos_i = interpolated_positions[i, t, :]
                pos_j = interpolated_positions[j, t, :]
                
                distance = np.sqrt((pos_i[0] - pos_j[0])**2 + (pos_i[1] - pos_j[1])**2)
                max_distance = max(max_distance, distance) 
    
    return max_distance


@njit(cache=True, fastmath=True)
def maximize_reward(paths_flat: np.ndarray, rvalues: np.ndarray) -> float:
    unique_elements = np.unique(paths_flat)
    reward = 0.0
    for element in unique_elements:
        reward += rvalues[element]
    return reward
