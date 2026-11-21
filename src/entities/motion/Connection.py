from dataclasses import dataclass

from .MotionPiece import MotionPiece


@dataclass(frozen=True)
class Connection:
    pieces: tuple[MotionPiece, ...]
    duration: float
