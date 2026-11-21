from dataclasses import dataclass

from ...core.problem.config import Vector, vector


@dataclass(frozen=True)
class MotionLimits:
    velocity: Vector = (3.0, 3.0)
    acceleration: Vector = (1.5, 1.5)

    def __post_init__(self):
        object.__setattr__(self, "velocity", vector(self.velocity))
        object.__setattr__(self, "acceleration", vector(self.acceleration))
        if min(*self.velocity, *self.acceleration) <= 0:
            raise ValueError("Axis limits must be positive")
