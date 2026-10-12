"""Seeded route, sequence, and related ruin-and-recreate moves."""

from dataclasses import replace
from math import hypot
from random import Random

from ..config import Config
from ..neighborhoods.common import fresh_id, normalize
from ..solution import Solution, Visit
from .neighborhoods.common import sample_candidates

RUIN_MODES = ("route", "sequence", "related")


def _task_positions(routes: list[list[Visit]]) -> list[tuple[int, int]]:
    return [
        (agent, visit_index)
        for agent, route in enumerate(routes)
        for visit_index in range(1, len(route) - 1)
        if route[visit_index].kind == "TASK"
    ]


def _ruin_route(routes, occupied, rng: Random) -> list[Visit]:
    agent = rng.choice([agent for agent, _ in occupied])
    removed = [visit for visit in routes[agent][1:-1] if visit.kind == "TASK"]
    routes[agent] = [
        routes[agent][0],
        *(visit for visit in routes[agent][1:-1] if visit.kind != "TASK"),
        routes[agent][-1],
    ]
    return removed


def _selected_positions(routes, occupied, mode, strength, rng: Random):
    agent, visit_index = rng.choice(occupied)
    if mode == "sequence":
        stop = min(len(routes[agent]) - 1, visit_index + strength + 1)
        return {(agent, index) for index in range(visit_index, stop)}
    anchor = routes[agent][visit_index].position
    nearby = sorted(
        occupied,
        key=lambda item: hypot(
            routes[item[0]][item[1]].position[0] - anchor[0],
            routes[item[0]][item[1]].position[1] - anchor[1],
        ),
    )
    return set(nearby[: strength + 1])


def _ruin_group(routes, occupied, mode, strength, rng: Random) -> list[Visit]:
    selected = _selected_positions(routes, occupied, mode, strength, rng)
    removed = [routes[agent][visit_index] for agent, visit_index in selected]
    for agent, visit_index in sorted(selected, reverse=True):
        routes[agent].pop(visit_index)
    return removed


def _detour(route: tuple[Visit, ...], visit_index: int, point) -> float:
    before = route[visit_index - 1].position
    after = route[visit_index].position
    return (
        hypot(before[0] - point[0], before[1] - point[1])
        + hypot(point[0] - after[0], point[1] - after[1])
        - hypot(before[0] - after[0], before[1] - after[1])
    )


def _recreate(
    ruined: Solution, removed: list[Visit], config: Config, rng: Random
) -> Solution:
    rebuilt = ruined
    for visit in rng.sample(removed, len(removed)):
        choices = (
            (agent, visit_index)
            for agent, route in enumerate(rebuilt.routes)
            for visit_index in range(1, len(route))
        )
        sampled = sample_candidates(choices, rng, config.recreate_sample_slots)
        if not sampled:
            break
        agent, visit_index = min(
            sampled,
            key=lambda item: (
                _detour(rebuilt.routes[item[0]], item[1], visit.position)
                + rng.random() * config.recreate_noise_scale
            ),
        )
        routes = [list(route) for route in rebuilt.routes]
        routes[agent].insert(
            visit_index,
            replace(
                visit,
                id=fresh_id(rebuilt, "repair"),
                velocity=(0.0, 0.0),
                wait=0.0,
            ),
        )
        rebuilt = normalize(routes, rebuilt.meetings)
    return rebuilt


def ruin_recreate(
    solution: Solution, config: Config, rng: Random, strength: int = 1
) -> Solution:
    """Apply one sampled destroy/repair move while preserving route endpoints."""
    routes = [list(route) for route in solution.routes]
    occupied = _task_positions(routes)
    if not occupied:
        return solution
    mode = rng.choice(RUIN_MODES)
    if mode == "route":
        removed = _ruin_route(routes, occupied, rng)
    else:
        removed = _ruin_group(routes, occupied, mode, strength, rng)
    ruined = normalize(routes, solution.meetings)
    return _recreate(ruined, removed, config, rng)
