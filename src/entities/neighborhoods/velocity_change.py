"""Change the menu velocity at one route visit; implements N17."""

from collections.abc import Iterator
from dataclasses import replace
from random import Random

from ...config import Config, Problem, Vector, velocity_menu
from ...solution import Solution
from .common import changed_connectors_feasible, edited, sample_candidates

name = "velocity_change"


def _proposals(
    solution: Solution, problem: Problem, config: Config
) -> Iterator[tuple[int, int, Vector]]:
    for agent, route in enumerate(solution.routes):
        menu = velocity_menu(problem.limits[agent], config)
        for visit_index, visit in enumerate(route[1:-1], 1):
            for velocity in menu:
                if velocity != visit.velocity:
                    route_copy = list(route)
                    route_copy[visit_index] = replace(visit, velocity=velocity)
                    if changed_connectors_feasible(
                        tuple(route_copy),
                        visit_index,
                        visit_index,
                        problem.limits[agent],
                    ):
                        yield agent, visit_index, velocity


def generate(
    solution: Solution,
    problem: Problem,
    config: Config,
    rng: Random,
) -> Iterator[Solution]:
    """Try alternative menu velocities at individual interior visits."""
    for agent, visit_index, velocity in sample_candidates(
        _proposals(solution, problem, config),
        rng,
        config.neighborhood_candidates,
    ):
        route = list(solution.routes[agent])
        route[visit_index] = replace(route[visit_index], velocity=velocity)
        yield edited(solution, agent, route)
