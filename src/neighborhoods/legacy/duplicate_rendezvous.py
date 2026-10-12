"""duplicate_rendezvous neighborhood. Deprecated; retained for historical runs."""

from random import Random
from typing import Iterator

from ...config import Config, Problem
from ...solution import Solution
from ..core import neighbors

NAME = "duplicate_rendezvous"


def generate(
    solution: Solution, problem: Problem, config: Config, rng: Random, **kwargs: object
) -> Iterator[Solution]:
    """Enumerate this family with an explicit random stream."""
    yield from neighbors(solution, problem, config, NAME, rng=rng, **kwargs)
