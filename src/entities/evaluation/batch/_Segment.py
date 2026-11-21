from dataclasses import dataclass


@dataclass(frozen=True)
class _Segment:
    batch: int
    pair: int
    left: float
    duration: float
    position: tuple[float, float]
    velocity: tuple[float, float]
    acceleration: tuple[float, float]
