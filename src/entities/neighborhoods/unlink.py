"""Sample free-visit removals; implements N11."""

from collections.abc import Iterator
from random import Random

from ...config import Config, Problem
from ...solution import Solution
from .common import edited, sample_candidates

name = "unlink"


def _free_proposals(solution: Solution):
    for agent, route in enumerate(solution.routes):
        for visit_index, visit in enumerate(route[:-1]):
            if visit.kind == "FREE":
                yield agent, visit_index


def generate(
    solution: Solution, problem: Problem, config: Config, rng: Random
) -> Iterator[Solution]:
    """Remove one FREE visit from a route."""
    proposals = _free_proposals(solution)
    for agent, visit_index in sample_candidates(
        proposals, rng, config.neighborhood_candidates
    ):
        route = list(solution.routes[agent])
        route.pop(visit_index)
        yield edited(solution, agent, route)
