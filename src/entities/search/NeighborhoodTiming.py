from dataclasses import dataclass


@dataclass
class NeighborhoodTiming:
    calls: int = 0
    total_seconds: float = 0.0
    shake_seconds: float = 0.0
    generation_seconds: float = 0.0
    evaluation_seconds: float = 0.0
