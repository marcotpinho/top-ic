"""All @njit-decorated functions, separated from class definitions.

These are the performance-critical inner loops used by the evaluator
and neighborhood operators. Keeping them in one file makes it clear
what's JIT-compiled and avoids Numba recompilation when classes change.
"""

import numpy as np
from numba import njit


# ======================== Evaluation kernels ========================

@njit(cache=True, fastmath=True)
def get_paths_max_length(paths_array, distmx):
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
def get_time_to_rewards(paths, speeds, distmx):
    all_times = []
    timestamps = []
    for i in range(len(paths)):
        path = paths[i]
        speed = speeds[i]
        path_times = [0.0]
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
def calculate_max_distance(interpolated_positions):
    if len(interpolated_positions) <= 1:
        return 0.0
    k, n, _ = interpolated_positions.shape
    max_distance = 0.0
    for i in range(k):
        for j in range(i + 1, k):
            for t in range(n):
                pos_i = interpolated_positions[i, t, :]
                pos_j = interpolated_positions[j, t, :]
                distance = np.sqrt(
                    (pos_i[0] - pos_j[0]) ** 2 + (pos_i[1] - pos_j[1]) ** 2
                )
                max_distance = max(max_distance, distance)
    return max_distance


@njit(cache=True, fastmath=True)
def maximize_reward(paths_flat, rvalues):
    unique_elements = np.unique(paths_flat)
    reward = 0.0
    for element in unique_elements:
        reward += rvalues[element]
    return reward


# ======================== RSSI kernel ========================

@njit(cache=True, fastmath=True)
def calculate_rssi_kernel(distance, tx_power, path_loss_exponent):
    if distance < 0.1:
        distance = 0.1
    return tx_power - 10 * path_loss_exponent * np.log10(distance)


# ======================== Operator kernels ========================

INVERSION_PROBABILITY = 0.75


@njit(cache=True)
def copy_paths(paths):
    return paths.copy()


@njit(cache=True)
def get_positive_indices(path):
    return np.where(path > 0)[0]


@njit(cache=True)
def get_negative_indices(path):
    return np.where(path < 0)[0]


@njit(cache=True, fastmath=True)
def two_opt_all_paths_core(paths):
    new_paths = copy_paths(paths)
    for agent_idx in range(len(new_paths)):
        path = new_paths[agent_idx]
        positive_indices = get_positive_indices(path)
        if len(positive_indices) < 2:
            continue
        pos1 = np.random.randint(0, len(positive_indices))
        pos2 = np.random.randint(0, len(positive_indices))
        if pos1 > pos2:
            pos1, pos2 = pos2, pos1
        if pos1 == pos2:
            continue
        positive_values = path[positive_indices].copy()
        positive_values[pos1 : pos2 + 1] = positive_values[pos1 : pos2 + 1][::-1]
        path[positive_indices] = positive_values
    return new_paths


@njit(cache=True, fastmath=True)
def invert_points_all_agents_core(paths):
    new_paths = copy_paths(paths)
    path_length = new_paths.shape[1]
    for agent_idx in range(len(new_paths)):
        points_to_invert = np.random.random(path_length) < INVERSION_PROBABILITY
        new_paths[agent_idx][points_to_invert] *= -1
    return new_paths


@njit(cache=True, fastmath=True)
def invert_points_all_agents_unique_core(paths):
    new_paths = copy_paths(paths)
    path_length = new_paths.shape[1]
    points_to_invert = np.random.random(path_length) < INVERSION_PROBABILITY
    for point_idx in np.where(points_to_invert)[0]:
        agents_with_point = np.where(new_paths[:, point_idx] > 0)[0]
        if len(agents_with_point) > 0:
            new_paths[agents_with_point, point_idx] *= -1
        new_agent = np.random.randint(0, len(new_paths))
        new_paths[new_agent, point_idx] = -new_paths[new_agent, point_idx]
    return new_paths
