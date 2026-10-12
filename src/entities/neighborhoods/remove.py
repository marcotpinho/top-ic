"""Sample task removals; implements the N2 structural edit."""

from collections.abc import Iterator
from random import Random

from ...config import Config, Problem
from ...solution import Solution
from .common import edited, sample_candidates

name = "remove"


def generate(
    solution: Solution, problem: Problem, config: Config, rng: Random
) -> Iterator[Solution]:
    """Remove one explicit TASK visit and reconstruct its route (eq. 1)."""
    proposals = (
        (agent, visit_index)
        for agent, route in enumerate(solution.routes)
        for visit_index in range(1, len(route) - 1)
        if route[visit_index].kind == "TASK"
    )
    for agent, visit_index in sample_candidates(
        proposals, rng, config.neighborhood_candidates
    ):
        route = list(solution.routes[agent])
        route.pop(visit_index)
        yield edited(solution, agent, route)
