"""Solution encoding for multi-agent routing optimization.

A solution is an M×(N-2) matrix where each row is an agent's path.
Positive values = visited (magnitude = visit order).
Negative values = not visited.
"""

import copy
import numpy as np
from topcc.config import ProblemContext


class Solution:

    def __init__(
        self,
        ctx: ProblemContext,
        distmx: np.ndarray = None,
        rvalues: np.ndarray = None,
        paths: np.ndarray = None,
        score: tuple = (-1, -1, -1),
    ):
        self.ctx = ctx
        self.score = score
        self.crowding_distance = -1
        self.visited = False
        self.dominated = True

        if paths is None:
            num_rewards = len(rvalues) - 2
            self.paths = self._init_paths_unique(num_rewards)
            self.paths = self._bound_all_paths(self.paths, distmx, rvalues)
        else:
            self.paths = paths

    # ==================== Path initialization ====================

    def _init_paths_unique(self, num_rewards: int) -> np.ndarray:
        paths = np.random.uniform(low=-1, high=0, size=(self.ctx.num_agents, num_rewards))
        positive_indices = np.random.randint(0, self.ctx.num_agents, size=(num_rewards))
        for reward_idx, agent_idx in enumerate(positive_indices):
            paths[agent_idx, reward_idx] = -paths[agent_idx, reward_idx]
        return paths

    # ==================== Pareto dominance ====================

    def dominates(self, other: "Solution") -> bool:
        if all(a == b for a, b in zip(self.score, other.score)):
            return True
        is_better_in_any = False
        for own_score, other_score in zip(self.score, other.score):
            if own_score > other_score:
                is_better_in_any = True
            elif own_score < other_score:
                return False
        return is_better_in_any

    # ==================== Path extraction ====================

    def get_solution_paths(self) -> list[np.ndarray]:
        trajectories = [self._get_sorted_indices(path) for path in self.paths]
        return [
            np.concatenate(([self.ctx.begin], traj, [self.ctx.end]))
            for traj in trajectories
        ]

    # ==================== Budget bounding ====================

    def _bound_all_paths(self, paths, distmx, rvalues):
        for agent_idx in range(len(paths)):
            paths[agent_idx] = self._bound_path(
                paths[agent_idx], self.ctx.budget[agent_idx], distmx, rvalues
            )
        return paths

    def _bound_path(self, path, budget, distmx, rvalues):
        positive_indices = np.where(path > 0)[0]
        trajectory = positive_indices[np.argsort(path[positive_indices])]
        if len(positive_indices) == 0:
            return path
        total_length = self._calculate_path_length(trajectory, distmx)
        while total_length > budget:
            impacts = self._calculate_removal_impacts(trajectory, distmx)
            reward_impact_ratio = impacts / rvalues[trajectory]
            probabilities = reward_impact_ratio / reward_impact_ratio.sum()
            removed_node_index = np.random.choice(trajectory, p=probabilities)
            path[removed_node_index] = -path[removed_node_index]
            trajectory = trajectory[trajectory != removed_node_index]
            if len(trajectory) == 0:
                break
            total_length = self._calculate_path_length(trajectory, distmx)
        return path

    def get_path_length(self, path, distmx):
        positive_indices = np.where(path > 0)[0]
        trajectory = positive_indices[np.argsort(path[positive_indices])]
        return self._calculate_path_length(trajectory, distmx)

    # ==================== Internal helpers ====================

    def _calculate_removal_impacts(self, trajectory, distmx):
        impacts = np.zeros(len(trajectory))
        for i, node_index in enumerate(trajectory):
            impacts[i] = self._calculate_single_node_impact(trajectory, i, node_index, distmx)
            if impacts[i] < 0:
                raise ValueError("Impacts must be >= 0.")
        return impacts

    def _calculate_single_node_impact(self, trajectory, position, node_index, distmx):
        begin, end = self.ctx.begin, self.ctx.end
        if position == 0:
            if len(trajectory) == 1:
                return (distmx[begin, node_index] + distmx[node_index, end]) - distmx[begin, end]
            else:
                next_node = trajectory[1]
                return (distmx[begin, node_index] + distmx[node_index, next_node]) - distmx[begin, next_node]
        elif position == len(trajectory) - 1:
            prev_node = trajectory[position - 1]
            return (distmx[prev_node, node_index] + distmx[node_index, end]) - distmx[prev_node, end]
        else:
            prev_node = trajectory[position - 1]
            next_node = trajectory[position + 1]
            return (distmx[prev_node, node_index] + distmx[node_index, next_node]) - distmx[prev_node, next_node] + 1e-6

    def _calculate_path_length(self, trajectory, distmx):
        begin, end = self.ctx.begin, self.ctx.end
        if len(trajectory) == 0:
            return distmx[begin, end]
        internal_length = 0.0
        if len(trajectory) > 1:
            internal_length = np.sum(distmx[trajectory[:-1], trajectory[1:]])
        return internal_length + distmx[begin, trajectory[0]] + distmx[trajectory[-1], end]

    def _get_sorted_indices(self, path):
        positive_indices = np.where(path > 0)[0]
        return positive_indices[np.argsort(path[positive_indices])]

    def copy(self) -> "Solution":
        return Solution(
            ctx=self.ctx,
            paths=np.copy(self.paths),
            score=copy.deepcopy(self.score),
        )

    def __repr__(self):
        return f"Solution(score={self.score})"
