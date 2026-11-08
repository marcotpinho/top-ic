"""Seeded sampling of feasible menu velocities for initial route seeds."""

from dataclasses import replace
from random import Random

from .config import Config, MotionLimits, velocity_menu
from .evaluation_core.trajectory import MotionError, State, connect
from .solution import Visit


def random_feasible_route_velocities(
    route: tuple[Visit, ...],
    limits: MotionLimits,
    config: Config,
    rng: Random,
) -> tuple[Visit, ...] | None:
    """Sample a feasible menu path, preserving endpoints.

    Backward reachability guarantees every sampled velocity has a feasible
    continuation to END. The method implements the connector constraints in
    eqs. (2)–(4) without minimizing route time.
    """
    choices = _velocity_choices(route, limits, config)
    successors = _feasible_successors(route, choices, limits)
    viable = _viable_choices(successors, choices)
    if not viable or not viable[0]:
        return None

    selected = [rng.choice(tuple(sorted(viable[0])))]
    for visit_index, layer in enumerate(successors):
        current_index = selected[-1]
        next_choices = [
            index
            for index in layer[current_index]
            if index in viable[visit_index + 1]
        ]
        if not next_choices:
            return None
        selected.append(rng.choice(next_choices))

    return tuple(
        replace(visit, velocity=choices[index][selected[index]])
        for index, visit in enumerate(route)
    )


def _velocity_choices(
    route: tuple[Visit, ...], limits: MotionLimits, config: Config
) -> tuple[tuple[tuple[float, float], ...], ...]:
    menu = velocity_menu(limits, config)
    choices = []
    for visit_index, visit in enumerate(route):
        if visit_index in (0, len(route) - 1):
            choices.append((visit.velocity,))
        else:
            choices.append(menu)
    return tuple(choices)


def _feasible_successors(
    route: tuple[Visit, ...],
    choices: tuple[tuple[tuple[float, float], ...], ...],
    limits: MotionLimits,
) -> list[list[list[int]]]:
    layers = []
    for visit_index, (start, end) in enumerate(zip(route, route[1:])):
        layer = []
        for start_velocity in choices[visit_index]:
            feasible = []
            for end_index, end_velocity in enumerate(choices[visit_index + 1]):
                try:
                    connect(
                        State(start.position, start_velocity),
                        State(end.position, end_velocity),
                        limits,
                    )
                except MotionError:
                    continue
                feasible.append(end_index)
            layer.append(feasible)
        layers.append(layer)
    return layers


def _viable_choices(
    successors: list[list[list[int]]],
    choices: tuple[tuple[tuple[float, float], ...], ...],
) -> list[set[int]]:
    viable = [set() for _ in choices]
    viable[-1] = set(range(len(choices[-1])))
    for visit_index in range(len(successors) - 1, -1, -1):
        viable[visit_index] = {
            start_index
            for start_index, next_indices in enumerate(successors[visit_index])
            if any(index in viable[visit_index + 1] for index in next_indices)
        }
    return viable


def initialize_solution_velocities(
    routes: tuple[tuple[Visit, ...], ...],
    limits: tuple[MotionLimits, ...],
    config: Config,
    rng: Random,
) -> tuple[tuple[Visit, ...], ...] | None:
    """Sample a feasible velocity path independently for every agent route."""
    initialized = []
    for route, agent_limits in zip(routes, limits):
        sampled = random_feasible_route_velocities(route, agent_limits, config, rng)
        if sampled is None:
            return None
        initialized.append(sampled)
    return tuple(initialized)
