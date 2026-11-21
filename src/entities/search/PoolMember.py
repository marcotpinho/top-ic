from dataclasses import dataclass

from ...solution import Solution


@dataclass
class PoolMember:
    solution: Solution
    age: int = 0
