"""Reverse one interior route segment with a 2-opt move."""

from collections.abc import Iterator
from random import Random

from ...config import Config, Problem
from ...solution import Solution
from .common import edited, sample_candidates

name = "two_opt"


def generate(
    solution: Solution, problem: Problem, config: Config, rng: Random
) -> Iterator[Solution]:
    proposals = (
        (agent, left, right)
        for agent, route in enumerate(solution.routes)
        for left in range(1, len(route) - 1)
        for right in range(left + 1, len(route) - 1)
    )
    for agent, left, right in sample_candidates(
        proposals, rng, config.neighborhood_candidates
    ):
        route = list(solution.routes[agent])
        route[left : right + 1] = reversed(route[left : right + 1])
        yield edited(solution, agent, route)
