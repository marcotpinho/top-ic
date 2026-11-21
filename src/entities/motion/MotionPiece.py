from dataclasses import dataclass

from ..problem.Config import Vector
from .State import State


@dataclass(frozen=True)
class MotionPiece:
    position: Vector
    velocity: Vector
    acceleration: Vector
    duration: float
    start_time: float = 0.0

    def state(self, t: float) -> State:
        return State(
            (
                self.position[0]
                + self.velocity[0] * t
                + 0.5 * self.acceleration[0] * t * t,
                self.position[1]
                + self.velocity[1] * t
                + 0.5 * self.acceleration[1] * t * t,
            ),
            (
                self.velocity[0] + self.acceleration[0] * t,
                self.velocity[1] + self.acceleration[1] * t,
            ),
        )
