"""Bounded physically valid candidates displaced from the epsilon front."""

from ..solution import Solution


class DominatedPool:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.solutions: list[Solution] = []
        self.keys: set[object] = set()

    def _order(self, solution: Solution) -> tuple:
        violation = solution.objectives[2]
        return (
            violation,
            solution.objectives[0],
            solution.objectives[1],
            repr(solution.key),
        )

    def update(self, displaced: list[Solution], front_keys: set[object]) -> None:
        """Keep distinct physical decisions outside the current front."""
        self.solutions = [item for item in self.solutions if item.key not in front_keys]
        self.keys = {item.key for item in self.solutions}
        for solution in displaced:
            if solution.key in front_keys or solution.key in self.keys:
                continue
            self.solutions.append(solution)
            self.keys.add(solution.key)
        self.solutions.sort(key=self._order)
        self.solutions = self.solutions[: self.capacity]
        self.keys = {item.key for item in self.solutions}
