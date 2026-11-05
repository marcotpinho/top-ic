"""Insert or relocate FREE visits around route segments; implements N19."""

from collections.abc import Iterator
from dataclasses import replace
from math import cos, hypot, sin, tau
from random import Random

from ...config import Config, Problem, Vector
from ...evaluation_core.trajectory import MotionError, State, connect
from ...solution import Solution, Visit
from .common import changed_connectors_feasible, edited, fresh_id, in_workspace

name = "free_segment"


def _sample_point(
    previous: Visit,
    following: Visit,
    problem: Problem,
    agent: int,
    config: Config,
    rng: Random,
) -> Vector:
    """Sample the actual connector in time and offset along its local normal."""
    connection = connect(
        State(previous.position, previous.velocity),
        State(following.position, following.velocity),
        problem.limits[agent],
    )
    time = rng.uniform(0.0, connection.duration)
    state = State(previous.position, previous.velocity)
    for piece in connection.pieces:
        if piece.start_time <= time <= piece.start_time + piece.duration:
            state = piece.state(time - piece.start_time)
            break
    direction = state.velocity
    length = hypot(*direction)
    if length <= config.geometry_tolerance:
        direction = tuple(b - a for a, b in zip(previous.position, following.position))
        length = hypot(*direction)
    if length <= config.geometry_tolerance:
        angle = rng.uniform(0.0, tau)
        direction, length = (cos(angle), sin(angle)), 1.0
    radius = config.free_segment_radius or config.comm_range
    offset = rng.uniform(-radius, radius)
    return (
        state.position[0] - offset * direction[1] / length,
        state.position[1] + offset * direction[0] / length,
    )


def _choices(solution: Solution) -> list[tuple[int, int, bool]]:
    """List every insertion slot and relocatable FREE visit."""
    choices = []
    for agent, route in enumerate(solution.routes):
        choices.extend((agent, index, False) for index in range(1, len(route)))
        choices.extend(
            (agent, index, True)
            for index, visit in enumerate(route[1:-1], 1)
            if visit.kind == "FREE"
        )
    return choices


def generate(
    solution: Solution,
    problem: Problem,
    config: Config,
    rng: Random,
) -> Iterator[Solution]:
    """Sample N19 insertions/relocations; preserve tasks and endpoint states.

    New FREE visits start stopped. Relocation preserves velocity and wait.
    Both adjacent connectors must be feasible; all randomness uses the run RNG.
    """
    choices = _choices(solution)
    if not choices:
        return
    seen = set()
    for _ in range(config.neighborhood_candidates):
        agent, index, relocate = rng.choice(choices)
        route = list(solution.routes[agent])
        visit = (
            route.pop(index)
            if relocate
            else Visit(fresh_id(solution, "segment-free"), "FREE", (0.0, 0.0))
        )
        try:
            point = _sample_point(
                route[index - 1], route[index], problem, agent, config, rng
            )
        except MotionError:
            continue
        if not in_workspace(point, config.waypoint_workspace):
            continue
        route.insert(index, replace(visit, position=point))
        if not changed_connectors_feasible(
            tuple(route), index, index, problem.limits[agent]
        ):
            continue
        candidate = edited(solution, agent, route)
        if candidate.key not in seen:
            seen.add(candidate.key)
            yield candidate
