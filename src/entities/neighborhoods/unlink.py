"""Sample meeting, free-visit, and wait removals; implements N11."""

from collections.abc import Iterator
from dataclasses import replace
from itertools import chain
from random import Random

from ...config import Config, Problem
from ...solution import Solution
from .common import edited, normalize, sample_candidates

name = "unlink"


def _free_and_wait_proposals(solution: Solution):
    for agent, route in enumerate(solution.routes):
        for visit_index, visit in enumerate(route[:-1]):
            if visit.kind == "FREE":
                yield "free", agent, visit_index
            if visit.wait > 0:
                yield "wait", agent, visit_index


def generate(
    solution: Solution, problem: Problem, config: Config, rng: Random
) -> Iterator[Solution]:
    """Remove one rendezvous decision and rebuild valid references (eq. 16)."""
    links = (("link", index, 0) for index in range(len(solution.meetings)))
    proposals = chain(links, _free_and_wait_proposals(solution))
    for kind, agent, visit_index in sample_candidates(
        proposals, rng, config.neighborhood_candidates
    ):
        if kind == "link":
            remaining = solution.meetings[:agent] + solution.meetings[agent + 1 :]
            yield normalize(solution.routes, remaining)
            continue
        route = list(solution.routes[agent])
        if kind == "free":
            route.pop(visit_index)
        else:
            route[visit_index] = replace(route[visit_index], wait=0.0)
        yield edited(solution, agent, route)
