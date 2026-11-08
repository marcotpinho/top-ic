"""Change one agent's visit speeds together while retaining nearby headings."""

from collections.abc import Iterator
from dataclasses import replace
from math import hypot
from random import Random

from ...config import Config, Problem, velocity_menu
from ...solution import Solution
from .common import changed_connectors_feasible, edited, sample_candidates

name = "velocity_agent"


def generate(
    solution: Solution, problem: Problem, config: Config, rng: Random
) -> Iterator[Solution]:
    proposals = (
        (agent, fraction)
        for agent, route in enumerate(solution.routes)
        if len(route) > 2
        for fraction in config.speed_fractions
    )
    seen = set()
    for agent, fraction in sample_candidates(
        proposals, rng, config.neighborhood_candidates
    ):
        route = list(solution.routes[agent])
        menu = velocity_menu(
            problem.limits[agent], replace(config, speed_fractions=(fraction,))
        )
        for index, visit in enumerate(route[1:-1], 1):
            velocity = max(
                menu,
                key=lambda value: (
                    sum(a * b for a, b in zip(value, visit.velocity)) / hypot(*value)
                ),
            )
            route[index] = replace(visit, velocity=velocity)
        if tuple(route) == solution.routes[agent]:
            continue
        if not changed_connectors_feasible(
            tuple(route), 1, len(route) - 2, problem.limits[agent]
        ):
            continue
        candidate = edited(solution, agent, route)
        if candidate.key not in seen:
            seen.add(candidate.key)
            yield candidate
