"""Shared occurrence-safe route edits and uniformly sampled candidates."""

from collections.abc import Iterable
from dataclasses import replace
from random import Random

from ...config import MotionLimits, Problem
from ...evaluation_core.trajectory import MotionError, State, connect
from ...solution import Solution, Visit


def normalize(routes: tuple | list) -> Solution:
    """Preserve routes while resolving duplicate visit occurrence IDs."""
    used = set()
    rebuilt = []
    for route in routes:
        row = []
        for visit in route:
            identity = visit.id
            if identity in used:
                suffix = 0
                while f"{identity}#{suffix}" in used:
                    suffix += 1
                identity = f"{identity}#{suffix}"
                visit = replace(visit, id=identity)
            used.add(identity)
            row.append(visit)
        rebuilt.append(tuple(row))
    return Solution(tuple(rebuilt))


def fresh_id(solution: Solution, prefix: str) -> str:
    """Choose an unused stable occurrence ID within the solution."""
    used = {visit.id for route in solution.routes for visit in route}
    index = 0
    while f"{prefix}:{index}" in used:
        index += 1
    return f"{prefix}:{index}"


def edited(solution: Solution, agent: int, route: tuple[Visit, ...]) -> Solution:
    """Replace one agent route while preserving the other route decisions."""
    routes = list(solution.routes)
    routes[agent] = tuple(route)
    return normalize(routes)


def in_workspace(point: tuple[float, float], workspace: tuple | None) -> bool:
    """Check a free point against the configured search workspace."""
    if workspace is None:
        return True
    xmin, xmax, ymin, ymax = workspace
    return xmin <= point[0] <= xmax and ymin <= point[1] <= ymax


def segment_projection(
    point: tuple[float, float], before: tuple[float, float], after: tuple[float, float]
) -> tuple[float, float]:
    """Project a point onto a closed route segment in Euclidean geometry."""
    direction = (after[0] - before[0], after[1] - before[1])
    length_squared = sum(component * component for component in direction)
    if length_squared == 0:
        return before
    fraction = (
        sum((point[axis] - before[axis]) * direction[axis] for axis in range(2))
        / length_squared
    )
    fraction = max(0.0, min(1.0, fraction))
    return tuple(before[axis] + fraction * direction[axis] for axis in range(2))


def changed_connectors_feasible(
    route: tuple[Visit, ...],
    first_changed_index: int,
    last_changed_index: int,
    limits: MotionLimits,
) -> bool:
    """Check route connectors touched by a contiguous velocity edit."""
    first_connector = max(0, first_changed_index - 1)
    last_connector = min(last_changed_index, len(route) - 2)
    for visit_index in range(first_connector, last_connector + 1):
        start = route[visit_index]
        end = route[visit_index + 1]
        try:
            connect(
                State(start.position, start.velocity),
                State(end.position, end.velocity),
                limits,
            )
        except MotionError:
            return False
    return True


def reached_task_ids(solution: Solution) -> set[str]:
    """Return the team union Q of explicit TASK visits in eq. (7)."""
    if solution.evaluation is not None:
        return set().union(*solution.evaluation.reached_tasks)
    return {
        visit.task_id
        for route in solution.routes
        for visit in route
        if visit.kind == "TASK"
    }


def unreached_tasks(solution: Solution, problem: Problem) -> tuple:
    """Return tasks absent from the team's explicit visits, eq. (7)."""
    reached = reached_task_ids(solution)
    return tuple(task for task in problem.tasks if task.id not in reached)


def sample_candidates[Candidate](
    proposals: Iterable[Candidate], rng: Random, cap: int
) -> list[Candidate]:
    """Uniformly sample at most cap proposals with O(cap) memory."""
    chosen: list[Candidate] = []
    for count, proposal in enumerate(proposals, 1):
        if len(chosen) < cap:
            chosen.append(proposal)
        else:
            index = rng.randrange(count)
            if index < cap:
                chosen[index] = proposal
    rng.shuffle(chosen)
    return chosen


__all__ = [
    "edited",
    "changed_connectors_feasible",
    "fresh_id",
    "in_workspace",
    "normalize",
    "reached_task_ids",
    "sample_candidates",
    "segment_projection",
    "unreached_tasks",
]
