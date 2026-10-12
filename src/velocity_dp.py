"""Deterministic finite-menu velocity refinement for a fixed visit sequence."""

from dataclasses import replace
from math import inf

from .config import velocity_menu
from .evaluation_core.trajectory import MotionError, State, connect


def refine_route_velocities(route, limits, config, forced_stops=()):
    """Return the minimum connector-time states, or None if no menu path exists.

    Existing waits and meeting endpoints are fixed to zero velocity. This DP
    optimizes travel time only; the full evaluator still decides reward,
    scheduled waiting, budgets, and communication feasibility.
    """
    forced_stops = set(forced_stops)
    menu = velocity_menu(limits, config)
    choices = []
    for k, visit in enumerate(route):
        if k in (0, len(route) - 1):
            choices.append((visit.velocity,))
        elif visit.wait > 0 or visit.id in forced_stops:
            choices.append(((0.0, 0.0),))
        else:
            choices.append(menu)

    costs = [0.0]
    predecessors = []
    for k in range(1, len(route)):
        next_costs = [inf] * len(choices[k])
        previous = [None] * len(choices[k])
        for j, velocity in enumerate(choices[k]):
            destination = State(route[k].position, velocity)
            for i, before_velocity in enumerate(choices[k - 1]):
                if costs[i] == inf:
                    continue
                try:
                    duration = connect(
                        State(route[k - 1].position, before_velocity),
                        destination,
                        limits,
                    ).duration
                except MotionError:
                    continue
                candidate = costs[i] + duration
                if candidate < next_costs[j]:
                    next_costs[j] = candidate
                    previous[j] = i
        costs = next_costs
        predecessors.append(previous)
    if not costs or all(cost == inf for cost in costs):
        return None
    state_index = min(range(len(costs)), key=lambda j: (costs[j], j))
    indices = [state_index]
    for previous in reversed(predecessors):
        state_index = previous[state_index]
        indices.append(state_index)
    indices.reverse()
    return tuple(
        replace(visit, velocity=choices[k][indices[k]]) for k, visit in enumerate(route)
    )
