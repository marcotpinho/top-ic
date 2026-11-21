from dataclasses import dataclass
from math import isfinite

from ...core.problem.config import Vector, vector


@dataclass(frozen=True)
class Task:
    id: str
    position: Vector
    reward: float

    def __post_init__(self):
        object.__setattr__(self, "position", vector(self.position))
        if not self.id or not isfinite(self.reward) or self.reward < 0:
            raise ValueError("Tasks need a stable ID and finite nonnegative reward")
