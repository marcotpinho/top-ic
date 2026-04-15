"""Multi-objective evaluation: reward, RSSI, path length."""

import numpy as np
from typing import List

from topcc.numba_kernels import (
    get_paths_max_length,
    get_time_to_rewards,
    calculate_max_distance,
    maximize_reward,
)
from topcc.solution import Solution
from topcc.rssi import LogDistanceRSSI


class Evaluator:

    def __init__(self, environment, rssi_model=None):
        self.env = environment
        self.rssi_model = rssi_model or LogDistanceRSSI()

    def evaluate(self, solutions: List[Solution] | Solution) -> None:
        if not isinstance(solutions, list):
            solutions = [solutions]
        if len(solutions) == 0:
            return

        for solution in solutions:
            paths = solution.get_solution_paths()
            paths_flat = np.concatenate(paths)

            total_reward = maximize_reward(paths_flat, self.env.rvalues)
            max_len = get_paths_max_length(paths, self.env.distmx)

            speeds = np.array(solution.ctx.speeds)
            interesting_times, _ = get_time_to_rewards(paths, speeds, self.env.distmx)
            interpolated_positions = self._interpolate_positions(paths, speeds, interesting_times)
            max_distance = calculate_max_distance(interpolated_positions)

            min_rssi = self.rssi_model.compute(max_distance, noise=False)
            solution.score = (total_reward, min_rssi, -max_len)

    def _interpolate_positions(self, paths, speeds, interesting_times):
        num_paths = len(paths)
        num_times = len(interesting_times)
        interpolated = np.zeros((num_paths, num_times, 2))

        for i in range(num_paths):
            path = paths[i]
            speed = speeds[i]
            if len(path) <= 1:
                continue

            time_to_rewards = np.zeros(len(path) - 1)
            cumulative_dist = 0.0
            for j in range(len(path) - 1):
                cumulative_dist += self.env.distmx[path[j], path[j + 1]]
                time_to_rewards[j] = cumulative_dist / speed

            x_positions = np.array([self.env.rpositions[path[j + 1], 0] for j in range(len(path) - 1)])
            y_positions = np.array([self.env.rpositions[path[j + 1], 1] for j in range(len(path) - 1)])

            for t in range(num_times):
                if len(time_to_rewards) > 0:
                    interpolated[i, t, 0] = np.interp(interesting_times[t], time_to_rewards, x_positions)
                    interpolated[i, t, 1] = np.interp(interesting_times[t], time_to_rewards, y_positions)

        return interpolated
