"""Add a feasible FREE visit near another agent's route; implements N16."""

from collections.abc import Iterator
from math import cos, sin, sqrt, tau
from random import Random

from ...config import Config, MotionLimits, Problem, Vector
from ...evaluation_core.trajectory import MotionError, State, connect
from ...solution import Solution, Visit
from .common import edited, fresh_id, in_workspace, sample_candidates

name = "free_near_visit"


def _sample_nearby_point(anchor: Vector, config: Config, rng: Random) -> Vector:
    """Sample uniformly inside the communication disk around an anchor."""
    angle = rng.uniform(0.0, tau)
    radius = config.comm_range * sqrt(rng.random())
    return (
        anchor[0] + radius * cos(angle),
        anchor[1] + radius * sin(angle),
    )


def _connector_feasible(
    route: tuple[Visit, ...],
    insertion_index: int,
    visit: Visit,
    limits: MotionLimits,
) -> bool:
    """Check both connectors adjacent to an inserted stopped visit."""
    previous = route[insertion_index - 1]
    following = route[insertion_index]
    try:
        connect(
            State(previous.position, previous.velocity),
            State(visit.position, visit.velocity),
            limits,
        )
        connect(
            State(visit.position, visit.velocity),
            State(following.position, following.velocity),
            limits,
        )
    except MotionError:
        return False
    return True


def _placements_for_anchor(
    solution: Solution,
    anchor_agent: int,
    anchor: Visit,
    problem: Problem,
    config: Config,
    rng: Random,
) -> Iterator[tuple[int, int, Vector]]:
    """Yield feasible target-route insertion slots for one source visit."""
    for target_agent, target_route in enumerate(solution.routes):
        if target_agent == anchor_agent:
            continue
        for insertion_index in range(1, len(target_route)):
            point = _sample_nearby_point(anchor.position, config, rng)
            if not in_workspace(point, config.waypoint_workspace):
                continue
            candidate_visit = Visit("candidate", "FREE", point)
            if _connector_feasible(
                target_route,
                insertion_index,
                candidate_visit,
                problem.limits[target_agent],
            ):
                yield target_agent, insertion_index, point


def _proposals(
    solution: Solution,
    problem: Problem,
    config: Config,
    rng: Random,
) -> Iterator[tuple[int, int, Vector]]:
    """Sample placements near visits belonging to other agents."""
    if config.comm_range == 0:
        return
    for anchor_agent, anchor_route in enumerate(solution.routes):
        for anchor in anchor_route:
            yield from _placements_for_anchor(
                solution,
                anchor_agent,
                anchor,
                problem,
                config,
                rng,
            )


def generate(
    solution: Solution,
    problem: Problem,
    config: Config,
    rng: Random,
) -> Iterator[Solution]:
    """Add one feasible FREE visit near a visit of a different agent."""
    for target_agent, insertion_index, point in sample_candidates(
        _proposals(solution, problem, config, rng),
        rng,
        config.neighborhood_candidates,
    ):
        route = list(solution.routes[target_agent])
        route.insert(
            insertion_index,
            Visit(fresh_id(solution, "nearby-free"), "FREE", point),
        )
        yield edited(solution, target_agent, route)
