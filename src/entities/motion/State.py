from dataclasses import dataclass

from ...core.problem.config import Vector, vector


@dataclass(frozen=True)
class State:
    position: Vector
    velocity: Vector = (0.0, 0.0)

    def __post_init__(self):
        object.__setattr__(self, "position", vector(self.position))
        object.__setattr__(self, "velocity", vector(self.velocity))
