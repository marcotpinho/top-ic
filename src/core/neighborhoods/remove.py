"""Sample task and free-waypoint removals."""

from collections.abc import Iterator
from random import Random

from ...entities.problem.Config import Config
from ...entities.problem.Problem import Problem
from ...entities.routing.Solution import Solution
from .common import edited, sample_candidates

name = "remove"


def generate(
    solution: Solution, problem: Problem, config: Config, rng: Random
) -> Iterator[Solution]:
    """Remove one TASK or FREE visit and reconstruct its route."""
    proposals = (
        (agent, visit_index)
        for agent, route in enumerate(solution.routes)
        for visit_index in range(1, len(route) - 1)
        if route[visit_index].kind in {"TASK", "FREE"}
    )
    for agent, visit_index in sample_candidates(
        proposals, rng, config.neighborhood_candidates
    ):
        route = list(solution.routes[agent])
        route.pop(visit_index)
        yield edited(solution, agent, route)
