"""Pareto front management with crowding distance selection."""

import numpy as np
from topcc.config import Config
from topcc.solution import Solution


class Archive:

    def __init__(self, config: Config):
        self.front: list[Solution] = []
        self.dominated: list[Solution] = []
        self.max_size = config.archive_size
        self.front_selection_prob = config.front_selection_prob

    def update_archive(self, neighbors: list[Solution]) -> None:
        all_solutions = self.front + self.dominated + neighbors
        self.front, all_dominated = self._fast_non_dominated_sort(all_solutions)

        if len(self.front) > self.max_size:
            self.front = self._select_by_crowding_distance(self.front, self.max_size)

        self.dominated = []
        if len(self.front) < self.max_size:
            keep = min(self.max_size - len(self.front), len(all_dominated))
            self.dominated = self._select_by_crowding_distance(all_dominated, keep)

    def select_solution_to_optimize(self, iteration: int) -> Solution:
        use_front = np.random.random() < self.front_selection_prob or not self.dominated
        candidates = self._get_available_candidates(
            self.front if use_front else self.dominated
        )
        if iteration % 2 == 0:
            solution = self._select_by_reward(candidates)
        else:
            solution = self._select_by_rssi(candidates)
        solution.visited = True
        return solution

    # ==================== Internal ====================

    def _fast_non_dominated_sort(self, solutions):
        n = len(solutions)
        if n <= 1:
            return solutions, []
        domination_count = [0] * n
        dominated_solutions = [[] for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                if solutions[i].dominates(solutions[j]):
                    dominated_solutions[i].append(j)
                    domination_count[j] += 1
                elif solutions[j].dominates(solutions[i]):
                    dominated_solutions[j].append(i)
                    domination_count[i] += 1
        non_dominated = []
        dominated = []
        for i in range(n):
            if domination_count[i] == 0:
                non_dominated.append(solutions[i])
            else:
                dominated.append(solutions[i])
        return non_dominated, dominated

    def _select_by_crowding_distance(self, solutions, k):
        self._assign_crowding_distance(solutions)
        solutions.sort(key=lambda s: s.crowding_distance, reverse=True)
        return solutions[:k]

    def _assign_crowding_distance(self, solutions):
        num = len(solutions)
        if num == 0:
            return
        for s in solutions:
            s.crowding_distance = 0
        for i in range(len(solutions[0].score)):
            solutions.sort(key=lambda s: s.score[i])
            solutions[0].crowding_distance = float("inf")
            solutions[-1].crowding_distance = float("inf")
            max_s = solutions[-1].score[i]
            min_s = solutions[0].score[i]
            if max_s == min_s:
                continue
            for j in range(1, num - 1):
                if solutions[j + 1].score[i] != solutions[j - 1].score[i]:
                    solutions[j].crowding_distance += (
                        solutions[j + 1].score[i] - solutions[j - 1].score[i]
                    ) / (max_s - min_s)

    def _get_available_candidates(self, solutions):
        candidates = [s for s in solutions if not s.visited]
        if not candidates:
            for s in solutions:
                s.visited = False
            candidates = solutions
        return candidates

    def _select_by_reward(self, candidates):
        rewards = np.array([s.score[0] for s in candidates])
        if rewards.sum() == 0:
            return np.random.choice(candidates)
        probabilities = rewards / np.sum(rewards)
        return np.random.choice(candidates, p=probabilities)

    def _select_by_rssi(self, candidates):
        rssi_scores = np.array([1 / s.score[1] for s in candidates])
        probabilities = rssi_scores / np.sum(rssi_scores)
        return np.random.choice(candidates, p=probabilities)
