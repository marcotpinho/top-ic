"""Sample shared-visit relays: turn a TASK visit into an offset FREE; implements N15."""

from collections.abc import Iterator
from math import cos, pi, sin
from random import Random

from ...config import Config, Problem
from ...solution import Solution, Visit
from .common import edited, fresh_id, in_workspace, sample_candidates

name = "relay"

DIRECTIONS = tuple((cos(k * pi / 4), sin(k * pi / 4)) for k in range(8))


def _shared_visits(solution: Solution) -> Iterator[tuple[int, int]]:
    """Yield TASK visits whose task another agent also visits, in any order."""
    visitors: dict[str, set[int]] = {}
    for agent, route in enumerate(solution.routes):
        for visit in route[1:-1]:
            if visit.kind == "TASK":
                visitors.setdefault(visit.task_id, set()).add(agent)
    for agent, route in enumerate(solution.routes):
        for visit_index, visit in enumerate(route[1:-1], 1):
            if visit.kind == "TASK" and visitors[visit.task_id] - {agent}:
                yield agent, visit_index


def _relay_proposals(solution: Solution, config: Config):
    for agent, visit_index in _shared_visits(solution):
        route = solution.routes[agent]
        if sum(visit.kind == "FREE" for visit in route) >= config.max_free_waypoints:
            continue
        x, y = route[visit_index].position
        for fraction in config.relay_radius_fractions:
            radius = fraction * config.comm_range
            for dx, dy in DIRECTIONS:
                point = (x + radius * dx, y + radius * dy)
                if in_workspace(point, config.waypoint_workspace):
                    yield agent, visit_index, point


def generate(
    solution: Solution, problem: Problem, config: Config, rng: Random
) -> Iterator[Solution]:
    """Replace a shared TASK occurrence with a nearby FREE visit (eqs. 7, 10)."""
    if len(solution.routes) < 2 or config.max_free_waypoints == 0:
        return
    for agent, visit_index, point in sample_candidates(
        _relay_proposals(solution, config), rng, config.neighborhood_candidates
    ):
        route = list(solution.routes[agent])
        # A fresh ID drops meetings tied to the task stop; the partner's TASK
        # occurrence keeps the team reward.
        route[visit_index] = Visit(fresh_id(solution, "relay"), "FREE", point)
        yield edited(solution, agent, route)
