"""C-TAEA-style coverage pool for valid solutions outside the feasible archive."""

from dataclasses import dataclass
from math import acos, hypot

from ..solution import Solution


@dataclass
class PoolMember:
    """Store one coverage candidate and its consecutive stale expansions."""

    solution: Solution
    cv: float
    reward: float
    mean_time: float
    subregion: int
    age: int = 0


class CoveragePool:
    """Bounded objective-space coverage independent of communication feasibility."""

    def __init__(self, capacity, divisions, max_age, total_reward, maximum_budget):
        self.capacity = capacity
        self.max_age = max_age
        self.total_reward = total_reward or 1.0
        self.maximum_budget = maximum_budget
        self.weights = tuple(
            (index / divisions, 1.0 - index / divisions)
            for index in range(divisions + 1)
        )
        self.members: list[PoolMember] = []
        self.entries = 0
        self.discards = 0
        self.age_discards = 0
        self.capacity_discards = 0
        self.front_transfers = 0

    @property
    def solutions(self) -> list[Solution]:
        return [member.solution for member in self.members]

    def normalized(self, solution: Solution) -> tuple[float, float]:
        return (
            min(1.0, max(0.0, 1.0 - solution.evaluation.reward / self.total_reward)),
            min(1.0, max(0.0, solution.objectives[1] / self.maximum_budget)),
        )

    def subregion(self, solution: Solution) -> int:
        point = self.normalized(solution)
        point_norm = hypot(*point)
        if point_norm == 0:
            return 0

        def angle(index: int) -> tuple[float, int]:
            weight = self.weights[index]
            cosine = sum(a * b for a, b in zip(point, weight))
            cosine /= point_norm * hypot(*weight)
            return acos(min(1.0, max(-1.0, cosine))), index

        return min(range(len(self.weights)), key=angle)

    def _member(self, solution: Solution, age: int = 0) -> PoolMember:
        return PoolMember(
            solution,
            solution.evaluation.comm_violation,
            solution.evaluation.reward,
            solution.objectives[1],
            self.subregion(solution),
            age,
        )

    def _ideal(self, front: list[Solution]) -> tuple[float, float]:
        source = front or self.solutions
        if not source:
            return (0.0, 0.0)
        points = [self.normalized(solution) for solution in source]
        return tuple(min(point[axis] for point in points) for axis in range(2))

    def _scalarization(self, member: PoolMember, ideal) -> float:
        point = self.normalized(member.solution)
        weight = self.weights[member.subregion]
        return max(
            max(weight[axis], 1e-12) * abs(point[axis] - ideal[axis])
            for axis in range(2)
        )

    @staticmethod
    def _nondominated(candidates: list[PoolMember]) -> list[PoolMember]:
        return [
            candidate
            for candidate in candidates
            if not any(
                other.solution.dominates(candidate.solution)
                for other in candidates
                if other.solution.key != candidate.solution.key
            )
        ]

    def update(self, candidates: list[Solution], front: list[Solution]) -> None:
        """Refill coverage rounds after merging retained and displaced candidates."""
        front_keys = {solution.key for solution in front}
        existing = {member.solution.key: member for member in self.members}
        merged = {}
        for solution in [*self.solutions, *candidates]:
            if solution.key in front_keys or solution.key in merged:
                continue
            previous = existing.get(solution.key)
            merged[solution.key] = self._member(
                solution, previous.age if previous is not None else 0
            )
        eligible = [member for member in merged.values() if member.age <= self.max_age]
        aged_out = len(merged) - len(eligible)
        front_occupancy = [0] * len(self.weights)
        for solution in front:
            front_occupancy[self.subregion(solution)] += 1
        ideal = self._ideal(front)
        selected = []
        round_index = 1
        while eligible and len(selected) < self.capacity:
            changed = False
            for region in range(len(self.weights)):
                allowance = max(0, round_index - front_occupancy[region])
                occupied = sum(item.subregion == region for item in selected)
                available = [item for item in eligible if item.subregion == region]
                while (
                    available and occupied < allowance and len(selected) < self.capacity
                ):
                    chosen = min(
                        self._nondominated(available),
                        key=lambda item: (
                            self._scalarization(item, ideal),
                            item.cv,
                            item.solution.objectives,
                            repr(item.solution.key),
                        ),
                    )
                    selected.append(chosen)
                    eligible.remove(chosen)
                    available.remove(chosen)
                    occupied += 1
                    changed = True
            if not changed and round_index > self.capacity + max(front_occupancy):
                break
            round_index += 1
        old_keys = set(existing)
        selected_keys = {member.solution.key for member in selected}
        self.entries += len(selected_keys - old_keys)
        front_transfers = len(old_keys & front_keys)
        capacity_discards = len(old_keys - selected_keys - front_keys)
        self.age_discards += aged_out
        self.capacity_discards += capacity_discards
        self.front_transfers += front_transfers
        self.discards += aged_out + capacity_discards
        self.members = selected

    def set_expansion_result(self, solution: Solution, improved: bool) -> None:
        """Reset or increment the selected member's consecutive stale age."""
        for member in self.members:
            if member.solution.key == solution.key:
                member.age = 0 if improved else member.age + 1
                break
        before = len(self.members)
        self.members = [member for member in self.members if member.age <= self.max_age]
        removed = before - len(self.members)
        self.age_discards += removed
        self.discards += removed

    def diagnostics(self) -> dict:
        occupancy = [0] * len(self.weights)
        for member in self.members:
            occupancy[member.subregion] += 1
        return {
            "size": len(self.members),
            "entries": self.entries,
            "discards": self.discards,
            "age_discards": self.age_discards,
            "capacity_discards": self.capacity_discards,
            "front_transfers": self.front_transfers,
            "subregion_occupancy": occupancy,
            "ages": [member.age for member in self.members],
        }
