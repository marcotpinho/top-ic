"""Partition and cooperative seed construction for the new Runner."""

from collections.abc import Iterator
from math import atan2, hypot
from random import Random
from typing import TYPE_CHECKING

from ..config import Problem, Task
from ..solution import Solution, Visit
from .neighborhoods.common import normalize

if TYPE_CHECKING:
    from .runner import Runner


def _partition_angle(task: Task, problem: Problem) -> tuple[float, str]:
    return (
        atan2(task.position[1] - problem.start[1], task.position[0] - problem.start[0]),
        task.id,
    )


def _build_partition(
    base: Solution, tasks: list[Task], shift: int, label: str
) -> Solution:
    routes = [list(route) for route in base.routes]
    for task_index, task in enumerate(tasks):
        agent = (task_index + shift) % len(routes)
        routes[agent].insert(
            -1,
            Visit(
                f"{label}:{agent}:{task.id}",
                "TASK",
                task.position,
                routes[agent][0].velocity,
                task_id=task.id,
            ),
        )
    return normalize(routes)


def partition_seeds(
    base: Solution, problem: Problem, rng: Random
) -> Iterator[Solution]:
    """Assign each TASK to one agent; reward remains a union (eq. 7)."""
    if not problem.tasks:
        return
    tasks = sorted(problem.tasks, key=lambda task: _partition_angle(task, problem))
    for shift in range(problem.num_agents):
        yield _build_partition(base, tasks, shift, "partition")
    shuffled = list(tasks)
    rng.shuffle(shuffled)
    yield _build_partition(base, shuffled, 0, "random-partition")


def density_seeds(base: Solution, problem: Problem) -> Iterator[Solution]:
    """Build task-rich routes by cheapest reward-normalized geometric insertion."""
    for reward_weighted in (True, False):
        routes = [list(route) for route in base.routes]
        remaining = list(problem.tasks)
        while remaining:
            choices = []
            for task in remaining:
                for agent, route in enumerate(routes):
                    for index in range(1, len(route)):
                        before = route[index - 1].position
                        after = route[index].position
                        detour = (
                            hypot(before[0] - task.position[0], before[1] - task.position[1])
                            + hypot(task.position[0] - after[0], task.position[1] - after[1])
                            - hypot(before[0] - after[0], before[1] - after[1])
                        )
                        score = detour / max(task.reward, 1e-12) if reward_weighted else detour
                        choices.append((score, -task.reward, task.id, agent, index, task))
            _, _, _, agent, index, task = min(choices)
            routes[agent].insert(
                index,
                Visit(
                    f"density:{int(reward_weighted)}:{agent}:{task.id}",
                    "TASK",
                    task.position,
                    routes[agent][0].velocity,
                    task_id=task.id,
                ),
            )
            remaining.remove(task)
        yield normalize(routes)


def cooperative_seeds(base: Solution, problem: Problem) -> Iterator[Solution]:
    """Give identical agents synchronized task orders for small Δ (eq. 15)."""
    if problem.num_agents < 2:
        return
    first_limit = problem.limits[0]
    first_velocity = problem.initial_velocities[0]
    if any(
        limit != first_limit or velocity != first_velocity
        for limit, velocity in zip(problem.limits, problem.initial_velocities)
    ):
        return
    tasks = sorted(
        problem.tasks,
        key=lambda task: (
            hypot(
                task.position[0] - problem.start[0], task.position[1] - problem.start[1]
            ),
            task.id,
        ),
    )
    yield _cooperative_subset(base, tasks)
    for subset in ([task] for task in tasks):
        yield _cooperative_subset(base, subset)


def _cooperative_subset(base: Solution, tasks: list[Task]) -> Solution:
    routes = [list(route) for route in base.routes]
    for agent, route in enumerate(routes):
        for task in tasks:
            route.insert(
                -1,
                Visit(
                    f"cooperative:{agent}:{task.id}",
                    "TASK",
                    task.position,
                    route[0].velocity,
                    task_id=task.id,
                ),
            )
    return normalize(routes)


def construct_reward_seed(runner: "Runner", base: Solution) -> None:
    """Grow a feasible task assignment from the direct route (eqs. 5 and 7)."""
    current = base
    while not runner.initialization_exhausted():
        candidates = []
        for solution in runner.neighborhood.generate(
            "insert", current, phase="seed_construction"
        ):
            result = runner.evaluate(solution, "construction")
            if result and result.evaluation.reward > current.evaluation.reward:
                candidates.append(result)
            if runner.initialization_exhausted():
                break
        if not candidates:
            break
        best_reward = max(item.evaluation.reward for item in candidates)
        eligible = [
            item for item in candidates if item.evaluation.reward == best_reward
        ]
        ranked = sorted(eligible, key=lambda item: (item.objectives[1], repr(item.key)))
        current = runner.rng.choice(ranked[: min(3, len(ranked))])
