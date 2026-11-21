"""Immutable ICC route decisions and their invariants."""

from .entities.problem.Problem import Problem
from .entities.routing.Solution import Solution
from .entities.routing.Visit import Visit


def direct_solution(problem: Problem) -> Solution:
    """Construct direct START-to-END routes for all agents."""
    return Solution(
        tuple(
            (
                Visit(
                    f"{m}:start", "START", problem.start, problem.initial_velocities[m]
                ),
                Visit(f"{m}:end", "END", problem.end, problem.initial_velocities[m]),
            )
            for m in range(problem.num_agents)
        )
    )
