"""Change velocities over a short route segment; implements N18."""

from collections.abc import Iterator
from dataclasses import replace
from random import Random

from ...config import Config, Problem, Vector, velocity_menu
from ...solution import Solution, Visit
from .common import changed_connectors_feasible, edited

name = "velocity_segment"


def _segments(
    solution: Solution, lengths: tuple[int, ...]
) -> list[tuple[int, int, int]]:
    """Return configured contiguous non-wait blocks."""
    segments = []
    for agent, route in enumerate(solution.routes):
        for length in lengths:
            for start_index in range(1, len(route) - length):
                block = route[start_index : start_index + length]
                if all(visit.wait == 0 for visit in block):
                    segments.append((agent, start_index, length))
    return segments


def _perturbed_route(
    route: tuple[Visit, ...],
    start_index: int,
    length: int,
    menu: tuple[Vector, ...],
    rng: Random,
) -> list[Visit] | None:
    changed = list(route)
    for visit_index in range(start_index, start_index + length):
        visit = changed[visit_index]
        alternatives = tuple(velocity for velocity in menu if velocity != visit.velocity)
        if not alternatives:
            return None
        changed[visit_index] = replace(visit, velocity=rng.choice(alternatives))
    return changed


def generate(
    solution: Solution,
    problem: Problem,
    config: Config,
    rng: Random,
) -> Iterator[Solution]:
    """Try seeded random velocity changes on contiguous visit blocks."""
    segments = _segments(solution, config.velocity_segment_lengths)
    if not segments:
        return
    seen: set[tuple] = set()
    for _ in range(config.neighborhood_candidates):
        agent, start_index, length = rng.choice(segments)
        menu = velocity_menu(problem.limits[agent], config)
        route = _perturbed_route(
            solution.routes[agent],
            start_index,
            length,
            menu,
            rng,
        )
        if route is None:
            continue
        if not changed_connectors_feasible(
            tuple(route),
            start_index,
            start_index + length - 1,
            problem.limits[agent],
        ):
            continue
        candidate = edited(solution, agent, route)
        if candidate.key in seen:
            continue
        seen.add(candidate.key)
        yield candidate
