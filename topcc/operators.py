"""Neighborhood operators for perturbation and local search."""

import numpy as np
from topcc.solution import Solution
from topcc.numba_kernels import (
    two_opt_all_paths_core,
    invert_points_all_agents_core,
    invert_points_all_agents_unique_core,
)

EPSILON = 1e-4


class Neighborhood:

    def __init__(self, algorithm: str = "unique_vis"):
        self._setup_operators(algorithm)
        self.num_neighborhoods = len(self.local_search_operators) * len(self.perturbation_operators)
        self.epsilon = EPSILON

    def _setup_operators(self, algorithm: str) -> None:
        if algorithm == "unique_vis":
            self.perturbation_operators = [
                self.invert_points_all_agents_unique,
                self.two_opt_all_paths,
            ]
            self.local_search_operators = [
                self.move_point,
                self.swap_points,
                self.invert_single_point_unique,
                self.add_and_move_unique,
                self.two_opt,
            ]
        else:
            self.perturbation_operators = [
                self.invert_points_all_agents,
                self.two_opt_all_paths,
            ]
            self.local_search_operators = [
                self.move_point,
                self.swap_points,
                self.invert_single_point,
                self.add_and_move,
                self.two_opt,
                self.path_relinking,
            ]

    def get_perturbation_operator(self):
        idx = np.random.randint(0, len(self.perturbation_operators))
        return self.perturbation_operators[idx]

    def get_local_search_operator(self, neighborhood: int):
        return self.local_search_operators[neighborhood % len(self.local_search_operators)]

    # ==================== Perturbation operators ====================

    def two_opt_all_paths(self, solution: Solution) -> Solution:
        new_solution = solution.copy()
        new_solution.paths = two_opt_all_paths_core(solution.paths)
        return new_solution

    def invert_points_all_agents(self, solution: Solution) -> Solution:
        new_solution = solution.copy()
        new_solution.paths = invert_points_all_agents_core(solution.paths)
        return new_solution

    def invert_points_all_agents_unique(self, solution: Solution) -> Solution:
        new_solution = solution.copy()
        new_solution.paths = invert_points_all_agents_unique_core(solution.paths)
        return new_solution

    # ==================== Local search operators ====================

    def move_point(self, solution: Solution, agent: int) -> list[Solution]:
        path = solution.paths[agent]
        positive_indices = self._get_positive_indices(path)
        if len(positive_indices) < 2:
            return []
        neighbors = []
        for source_idx in range(len(positive_indices)):
            source_value = path[positive_indices[source_idx]]
            for target_idx in range(len(positive_indices)):
                if source_idx == target_idx:
                    continue
                new_solution = solution.copy()
                new_path = new_solution.paths[agent]
                positive_values = new_path[positive_indices].copy()
                positive_values = np.delete(positive_values, source_idx)
                insertion_position = target_idx if target_idx < source_idx else target_idx - 1
                positive_values = np.insert(positive_values, insertion_position, source_value)
                new_path[positive_indices] = positive_values
                neighbors.append(new_solution)
        return neighbors

    def swap_points(self, solution: Solution, agent: int) -> list[Solution]:
        path = solution.paths[agent]
        positive_indices = self._get_positive_indices(path)
        neighbors = []
        for i in range(len(positive_indices)):
            for j in range(i + 1, len(positive_indices)):
                new_solution = solution.copy()
                new_path = new_solution.paths[agent]
                new_path[positive_indices[i]], new_path[positive_indices[j]] = (
                    new_path[positive_indices[j]],
                    new_path[positive_indices[i]],
                )
                neighbors.append(new_solution)
        return neighbors

    def two_opt(self, solution: Solution, agent: int) -> list[Solution]:
        path = solution.paths[agent]
        positive_indices = self._get_positive_indices(path)
        if len(positive_indices) < 2:
            return []
        neighbors = []
        for i in range(len(positive_indices) - 1):
            for j in range(i + 1, len(positive_indices)):
                new_solution = solution.copy()
                new_path = new_solution.paths[agent]
                indices_to_reverse = positive_indices[i : j + 1]
                new_path[indices_to_reverse] = new_path[indices_to_reverse][::-1].copy()
                neighbors.append(new_solution)
        return neighbors

    def invert_single_point(self, solution: Solution, agent: int) -> list[Solution]:
        path = solution.paths[agent]
        neighbors = []
        for i in range(len(path)):
            new_solution = solution.copy()
            new_solution.paths[agent][i] *= -1
            neighbors.append(new_solution)
        return neighbors

    def invert_single_point_unique(self, solution: Solution, agent: int) -> list[Solution]:
        return self._add_point_unique(solution, agent) + self._remove_point(solution, agent)

    def _add_point_unique(self, solution: Solution, agent: int) -> list[Solution]:
        path = solution.paths[agent]
        negative_indices = self._get_negative_indices(path)
        neighbors = []
        for point_idx in negative_indices:
            new_solution = solution.copy()
            positive_agents = np.where(new_solution.paths[:, point_idx] > 0)[0]
            new_solution.paths[positive_agents, point_idx] *= -1
            new_solution.paths[agent][point_idx] *= -1
            neighbors.append(new_solution)
        return neighbors

    def _remove_point(self, solution: Solution, agent: int) -> list[Solution]:
        path = solution.paths[agent]
        positive_indices = self._get_positive_indices(path)
        neighbors = []
        for point_idx in positive_indices:
            new_solution = solution.copy()
            new_solution.paths[agent][point_idx] = -new_solution.paths[agent][point_idx]
            neighbors.append(new_solution)
        return neighbors

    def add_and_move(self, solution: Solution, agent: int) -> list[Solution]:
        path = solution.paths[agent]
        negative_indices = self._get_negative_indices(path)
        neighbors = []
        for add_idx in negative_indices:
            temp = solution.copy()
            temp.paths[agent][add_idx] *= -1
            new_pos = self._get_positive_indices(temp.paths[agent])
            source_value = temp.paths[agent][add_idx]
            for target_idx in new_pos:
                if add_idx == target_idx:
                    continue
                new_solution = temp.copy()
                new_path = new_solution.paths[agent]
                positive_values = new_path[new_pos].copy()
                src_rel = np.where(new_pos == add_idx)[0][0]
                tgt_rel = np.where(new_pos == target_idx)[0][0]
                positive_values = np.delete(positive_values, src_rel)
                insert_pos = tgt_rel if tgt_rel < src_rel else tgt_rel - 1
                positive_values = np.insert(positive_values, insert_pos, source_value)
                new_path[new_pos] = positive_values
                neighbors.append(new_solution)
        return neighbors

    def add_and_move_unique(self, solution: Solution, agent: int) -> list[Solution]:
        path = solution.paths[agent]
        negative_indices = self._get_negative_indices(path)
        neighbors = []
        for add_idx in negative_indices:
            temp = solution.copy()
            positive_agents = np.where(temp.paths[:, add_idx] > 0)[0]
            temp.paths[positive_agents, add_idx] *= -1
            temp.paths[agent][add_idx] *= -1
            new_pos = self._get_positive_indices(temp.paths[agent])
            source_value = temp.paths[agent][add_idx]
            for target_idx in new_pos:
                if add_idx == target_idx:
                    continue
                new_solution = temp.copy()
                new_path = new_solution.paths[agent]
                positive_values = new_path[new_pos].copy()
                src_rel = np.where(new_pos == add_idx)[0][0]
                tgt_rel = np.where(new_pos == target_idx)[0][0]
                positive_values = np.delete(positive_values, src_rel)
                insert_pos = tgt_rel if tgt_rel < src_rel else tgt_rel - 1
                positive_values = np.insert(positive_values, insert_pos, source_value)
                new_path[new_pos] = positive_values
                neighbors.append(new_solution)
        return neighbors

    def path_relinking(self, solution: Solution, agent: int) -> list[Solution]:
        path = solution.paths[agent]
        neighbors = []
        for other_agent in range(len(solution.paths)):
            if other_agent == agent:
                continue
            num_changes = np.random.randint(1, len(path))
            indices_to_change = np.random.choice(range(len(path)), size=num_changes, replace=False)
            for point_idx in indices_to_change:
                if solution.paths[other_agent][point_idx] == path[point_idx]:
                    continue
                new_solution = solution.copy()
                new_solution.paths[other_agent][point_idx] = (
                    path[point_idx] + np.random.random() * self.epsilon
                )
                neighbors.append(new_solution)
        return neighbors

    # ==================== Utilities ====================

    def _get_positive_indices(self, path):
        return np.where(path > 0)[0]

    def _get_negative_indices(self, path):
        return np.where(path < 0)[0]


def local_search(solution, neighborhood, neighborhood_id):
    neighbors = []
    for agent in range(len(solution.paths)):
        operator = neighborhood.get_local_search_operator(neighborhood_id)
        neighbors.extend(operator(solution, agent))
    return neighbors


def perturb_solution(solution, neighborhood):
    operator = neighborhood.get_perturbation_operator()
    return operator(solution)
