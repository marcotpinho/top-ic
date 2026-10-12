"""Sample task substitutions; implements the N3 structural edit."""

from collections.abc import Iterator
from random import Random

from ...config import Config, Problem
from ...solution import Solution, Visit
from .common import edited, fresh_id, sample_candidates, unreached_tasks

name = "replace"


def generate(
    solution: Solution, problem: Problem, config: Config, rng: Random
) -> Iterator[Solution]:
    """Replace a TASK occurrence with an unreached TASK (eqs. 1 and 7)."""
    proposals = (
        (agent, visit_index, task)
        for task in unreached_tasks(solution, problem)
        for agent, route in enumerate(solution.routes)
        for visit_index in range(1, len(route) - 1)
        if route[visit_index].kind == "TASK"
    )
    for agent, visit_index, task in sample_candidates(
        proposals, rng, config.neighborhood_candidates
    ):
        route = list(solution.routes[agent])
        route[visit_index] = Visit(
            fresh_id(solution, "replace"), "TASK", task.position, task_id=task.id
        )
        yield edited(solution, agent, route)
