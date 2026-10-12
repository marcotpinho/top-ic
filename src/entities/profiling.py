"""Wall-clock accumulators for the ICC search.

All durations use perf_counter seconds. Family total includes shaking,
generation, and evaluation. The shake duration covers perturbation only;
its later candidate evaluation is included in evaluation_seconds.
"""

from dataclasses import dataclass, field


@dataclass
class NeighborhoodTiming:
    calls: int = 0
    total_seconds: float = 0.0
    shake_seconds: float = 0.0
    generation_seconds: float = 0.0
    evaluation_seconds: float = 0.0


@dataclass
class SearchProfile:
    search_loop_seconds: float = 0.0
    evaluation_seconds: float = 0.0
    evaluator_seconds: float = 0.0
    neighborhoods: dict[str, NeighborhoodTiming] = field(default_factory=dict)

    @classmethod
    def for_neighborhoods(cls, names: tuple[str, ...]) -> "SearchProfile":
        """Initialize one timing row for every enabled ICC family."""
        return cls(neighborhoods={name: NeighborhoodTiming() for name in names})
