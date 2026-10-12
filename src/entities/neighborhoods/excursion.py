"""Sample split-and-rejoin bypasses; implements N14."""

from collections import defaultdict
from collections.abc import Iterator
from itertools import chain
from random import Random

from ...config import Config, Problem
from ...solution import Solution
from .common import edited, sample_candidates

name = "excursion"


def _duplicates(solution: Solution) -> Iterator[tuple[str, int, int, int]]:
    occurrences: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for agent, route in enumerate(solution.routes):
        for visit_index, visit in enumerate(route[1:-1], 1):
            if visit.kind == "TASK" and visit.task_id is not None:
                occurrences[visit.task_id].append((agent, visit_index))
    for locations in occurrences.values():
        if len(locations) > 1:
            for agent, visit_index in locations:
                yield "duplicate", agent, visit_index, 0


def _shared_task_ids(route, partner_route) -> set[str]:
    own = {visit.task_id for visit in route if visit.kind == "TASK"}
    other = {visit.task_id for visit in partner_route if visit.kind == "TASK"}
    return own & other


def _bypasses(
    solution: Solution, config: Config
) -> Iterator[tuple[str, int, int, int]]:
    for agent, route in enumerate(solution.routes):
        for other_agent, partner_route in enumerate(solution.routes):
            if agent == other_agent:
                continue
            shared = _shared_task_ids(route, partner_route)
            for left in range(1, len(route) - 2):
                if route[left].task_id not in shared:
                    continue
                last = min(len(route) - 1, left + config.excursion_max_bypass_tasks + 2)
                for right in range(left + 2, last):
                    if route[right].task_id in shared:
                        yield "bypass", agent, left, right


def generate(
    solution: Solution, problem: Problem, config: Config, rng: Random
) -> Iterator[Solution]:
    """Bypass short shared-route portions, reconstructing motion (eqs. 1–4)."""
    proposals = chain(_duplicates(solution), _bypasses(solution, config))
    for kind, agent, left, right in sample_candidates(
        proposals, rng, config.neighborhood_candidates
    ):
        route = list(solution.routes[agent])
        if kind == "duplicate":
            route.pop(left)
        else:
            del route[left + 1 : right]
        yield edited(solution, agent, route)
