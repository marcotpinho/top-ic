from dataclasses import dataclass

from ..routing.Solution import Solution


@dataclass
class PoolMember:
    solution: Solution
    age: int = 0
