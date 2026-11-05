"""Seeded 10–40% ruin and regret-2 recreation for explicit task visits."""

from dataclasses import replace
from math import ceil, hypot
from random import Random

from ..config import Config
from ..solution import Solution, Visit
from .neighborhoods.common import fresh_id, normalize

RUIN_MODES = ("route", "region_sequences", "related")


def _task_positions(solution: Solution) -> list[tuple[int, int]]:
    return [
        (agent, visit_index)
        for agent, route in enumerate(solution.routes)
        for visit_index, visit in enumerate(route[1:-1], 1)
        if visit.kind == "TASK"
    ]


def _removal_count(total: int, rng: Random) -> int:
    fraction = rng.uniform(0.1, 0.4)
    return min(total, max(1, ceil(total * fraction)))


def _visit_time(solution: Solution, item: tuple[int, int]) -> float:
    if solution.evaluation is None or not solution.evaluation.visit_times:
        return float(item[1])
    return solution.evaluation.visit_times[item[0]][item[1]][0]


def _route_positions(solution, occupied, count, rng):
    agent = rng.choice(sorted({agent for agent, _ in occupied}))
    candidates = [item for item in occupied if item[0] == agent]
    rng.shuffle(candidates)
    if len(candidates) < count:
        remainder = [item for item in occupied if item[0] != agent]
        rng.shuffle(remainder)
        candidates.extend(remainder)
    return candidates[:count]


def _region_sequences(solution, occupied, count, rng):
    anchor = rng.choice(occupied)
    point = solution.routes[anchor[0]][anchor[1]].position
    selected = []
    for agent in range(len(solution.routes)):
        route_items = [item for item in occupied if item[0] == agent]
        route_items.sort(
            key=lambda item: hypot(
                solution.routes[item[0]][item[1]].position[0] - point[0],
                solution.routes[item[0]][item[1]].position[1] - point[1],
            )
        )
        if route_items:
            center = route_items[0][1]
            selected.extend(
                sorted(route_items, key=lambda item: abs(item[1] - center))[:2]
            )
    selected = sorted(
        set(selected),
        key=lambda item: hypot(
            solution.routes[item[0]][item[1]].position[0] - point[0],
            solution.routes[item[0]][item[1]].position[1] - point[1],
        ),
    )
    return selected[:count]


def _related_positions(solution, occupied, count, rng):
    anchor = rng.choice(occupied)
    anchor_visit = solution.routes[anchor[0]][anchor[1]]
    anchor_time = _visit_time(solution, anchor)
    spatial_scale = (
        max(
            (
                hypot(
                    solution.routes[item[0]][item[1]].position[0]
                    - anchor_visit.position[0],
                    solution.routes[item[0]][item[1]].position[1]
                    - anchor_visit.position[1],
                )
                for item in occupied
            ),
            default=1.0,
        )
        or 1.0
    )
    time_scale = (
        max(
            (abs(_visit_time(solution, item) - anchor_time) for item in occupied),
            default=1.0,
        )
        or 1.0
    )
    return sorted(
        occupied,
        key=lambda item: (
            hypot(
                solution.routes[item[0]][item[1]].position[0]
                - anchor_visit.position[0],
                solution.routes[item[0]][item[1]].position[1]
                - anchor_visit.position[1],
            )
            / spatial_scale
            + abs(_visit_time(solution, item) - anchor_time) / time_scale
        ),
    )[:count]


def _ruin(solution: Solution, rng: Random) -> tuple[Solution, list[Visit]]:
    occupied = _task_positions(solution)
    if not occupied:
        return solution, []
    count = _removal_count(len(occupied), rng)
    mode = rng.choice(RUIN_MODES)
    if mode == "route":
        selected = _route_positions(solution, occupied, count, rng)
    elif mode == "region_sequences":
        selected = _region_sequences(solution, occupied, count, rng)
    else:
        selected = _related_positions(solution, occupied, count, rng)
    routes = [list(route) for route in solution.routes]
    removed = [routes[agent][visit_index] for agent, visit_index in selected]
    for agent, visit_index in sorted(selected, reverse=True):
        routes[agent].pop(visit_index)
    return normalize(routes), removed


def _detour(route: tuple[Visit, ...], index: int, point) -> float:
    before = route[index - 1].position
    after = route[index].position
    return (
        hypot(before[0] - point[0], before[1] - point[1])
        + hypot(point[0] - after[0], point[1] - after[1])
        - hypot(before[0] - after[0], before[1] - after[1])
    )


def _recreate(solution, removed, config, rng):
    rebuilt = solution
    unique = {visit.task_id: visit for visit in removed}
    while unique:
        present = {
            visit.task_id
            for route in rebuilt.routes
            for visit in route
            if visit.kind == "TASK"
        }
        options_by_task = {}
        for task_id, visit in unique.items():
            if task_id in present:
                continue
            options = []
            for agent, route in enumerate(rebuilt.routes):
                for index in range(1, len(route)):
                    cost = _detour(route, index, visit.position)
                    cost += rng.random() * config.recreate_noise_scale
                    options.append((cost, agent, index))
            options_by_task[task_id] = sorted(options)
        if not options_by_task:
            break
        task_id = max(
            options_by_task,
            key=lambda key: (
                options_by_task[key][1][0] - options_by_task[key][0][0]
                if len(options_by_task[key]) > 1
                else float("inf")
            ),
        )
        _, agent, index = options_by_task[task_id][0]
        visit = unique.pop(task_id)
        routes = [list(route) for route in rebuilt.routes]
        routes[agent].insert(
            index,
            replace(
                visit,
                id=fresh_id(rebuilt, "recreate"),
                velocity=(0.0, 0.0),
                wait=0.0,
            ),
        )
        rebuilt = normalize(routes)
    return rebuilt


def ruin_recreate(
    solution: Solution, config: Config, rng: Random, strength: int = 1
) -> Solution:
    """Destroy 10–40% of task visits and rebuild with regret-2 insertion."""
    ruined, removed = _ruin(solution, rng)
    return _recreate(ruined, removed, config, rng)
