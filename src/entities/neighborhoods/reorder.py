"""Sample route reorderings; implements the N4 structural edits."""

from collections.abc import Iterator
from random import Random

from ...config import Config, Problem
from ...solution import Solution
from .common import edited, sample_candidates

name = "reorder"
KINDS = ("relocate", "swap", "reverse")


def generate(
    solution: Solution, problem: Problem, config: Config, rng: Random
) -> Iterator[Solution]:
    """Relocate, swap, or reverse visits while retaining fixed endpoints (eq. 1)."""
    proposals = (
        (kind, agent, left, right)
        for kind in KINDS
        for agent, route in enumerate(solution.routes)
        for left in range(1, len(route) - 1)
        for right in range(left + 1, len(route) - 1)
    )
    for kind, agent, left, right in sample_candidates(
        proposals, rng, config.neighborhood_candidates
    ):
        route = list(solution.routes[agent])
        if kind == "relocate":
            route.insert(right, route.pop(left))
        elif kind == "swap":
            route[left], route[right] = route[right], route[left]
        else:
            route[left : right + 1] = reversed(route[left : right + 1])
        yield edited(solution, agent, route)
