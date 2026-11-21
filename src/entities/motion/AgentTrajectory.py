from dataclasses import dataclass

from ...core.motion.constants import TOL
from .MotionPiece import MotionPiece
from .State import State


@dataclass(frozen=True)
class AgentTrajectory:
    pieces: tuple[MotionPiece, ...]
    completion_time: float
    start: State
    end: State

    def state(self, t: float) -> State:
        if t < 0:
            raise ValueError("Time must be nonnegative")
        if t > self.completion_time:
            return State(self.end.position, (0.0, 0.0))
        if t == self.completion_time:
            return self.end
        for piece in self.pieces:
            if piece.start_time <= t <= piece.start_time + piece.duration + TOL:
                return piece.state(min(piece.duration, max(0.0, t - piece.start_time)))
        return self.start
