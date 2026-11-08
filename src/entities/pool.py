"""Bounded Pareto archive in communication violation, negative reward, and time."""

from dataclasses import dataclass

from ..solution import Solution
from .selection import crowding_distances, nondominated, pool_vector


@dataclass
class PoolMember:
    solution: Solution
    age: int = 0


class ParetoPool:
    def __init__(self, capacity: int, max_age: int):
        self.capacity = capacity
        self.max_age = max_age
        self.members: list[PoolMember] = []
        self.entries = 0
        self.discards = 0
        self.age_discards = 0
        self.dominance_discards = 0
        self.capacity_discards = 0
        self.front_transfers = 0

    @property
    def solutions(self) -> list[Solution]:
        return [member.solution for member in self.members]

    def update(self, candidates: list[Solution], front: list[Solution]) -> None:
        front_keys = {solution.key for solution in front}
        existing = {member.solution.key: member for member in self.members}
        merged = {}
        for solution in [*self.solutions, *candidates]:
            if solution.key not in front_keys and solution.key not in merged:
                merged[solution.key] = existing.get(solution.key, PoolMember(solution))
        eligible = [member for member in merged.values() if member.age <= self.max_age]
        aged_out = len(merged) - len(eligible)
        survivors = nondominated([member.solution for member in eligible], pool_vector)
        dominance_discards = len(eligible) - len(survivors)
        capacity_discards = max(0, len(survivors) - self.capacity)
        if capacity_discards:
            crowding = crowding_distances(survivors, pool_vector)
            survivors.sort(
                key=lambda solution: (-crowding[solution.key], repr(solution.key))
            )
            survivors = survivors[: self.capacity]
        selected_keys = {solution.key for solution in survivors}
        self.entries += len(selected_keys - existing.keys())
        self.age_discards += aged_out
        self.dominance_discards += dominance_discards
        self.capacity_discards += capacity_discards
        self.front_transfers += len(existing.keys() & front_keys)
        self.discards += aged_out + dominance_discards + capacity_discards
        self.members = [merged[solution.key] for solution in survivors]

    def set_expansion_result(self, solution: Solution, improved: bool) -> None:
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
        return {
            "size": len(self.members),
            "entries": self.entries,
            "discards": self.discards,
            "age_discards": self.age_discards,
            "dominance_discards": self.dominance_discards,
            "capacity_discards": self.capacity_discards,
            "front_transfers": self.front_transfers,
            "ages": [member.age for member in self.members],
        }
