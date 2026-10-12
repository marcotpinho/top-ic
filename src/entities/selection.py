"""Seeded base selection from the epsilon front or dominated pool."""

from random import Random

from ..solution import Solution


def select_base(
    front: list[Solution],
    pool: list[Solution],
    iteration: int,
    front_probability: float,
    rng: Random,
) -> Solution:
    """Cycle objective preferences and sample one of the five best seeds."""
    if pool and rng.random() >= front_probability:
        source = pool
    else:
        source = front or pool
    if not source:
        raise ValueError("Cannot select from an empty archive")
    if iteration % 3 == 0:
        ranked = sorted(source, key=lambda solution: solution.objectives[:2])
    elif iteration % 3 == 1:
        ranked = sorted(
            source,
            key=lambda solution: (solution.objectives[2], solution.objectives[0]),
        )
    else:
        ranked = sorted(
            source,
            key=lambda solution: (solution.objectives[1], solution.objectives[0]),
        )
    return rng.choice(ranked[: min(5, len(ranked))])
