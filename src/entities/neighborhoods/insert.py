"""Sample task insertions; implements the N1 structural edit."""

from collections.abc import Iterator
from random import Random

from ...config import Config, Problem
from ...solution import Solution, Visit
from .common import edited, fresh_id, sample_candidates, unreached_tasks

name = "insert"


def generate(
    solution: Solution, problem: Problem, config: Config, rng: Random
) -> Iterator[Solution]:
    """Insert one unreached TASK, preserving explicit reward accounting (eq. 7)."""
    proposals = (
        (agent, visit_index, task)
        for task in unreached_tasks(solution, problem)
        for agent, route in enumerate(solution.routes)
        for visit_index in range(1, len(route))
    )
    for agent, visit_index, task in sample_candidates(
        proposals, rng, config.neighborhood_candidates
    ):
        route = list(solution.routes[agent])
        route.insert(
            visit_index,
            Visit(fresh_id(solution, "insert"), "TASK", task.position, task_id=task.id),
        )
        yield edited(solution, agent, route)
