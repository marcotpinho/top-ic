"""Shared, occurrence-preserving neighborhood operations."""

from dataclasses import replace

from ..solution import Meeting, Solution, Visit


def normalize(routes: tuple | list, meetings: tuple[Meeting, ...] = ()) -> Solution:
    """Preserve occurrence IDs, resolving collisions and dangling meetings."""
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
    ownership = {
        visit.id: agent for agent, route in enumerate(rebuilt) for visit in route
    }
    kept = tuple(
        pair
        for pair in meetings
        if pair.left in used
        and pair.right in used
        and ownership[pair.left] != ownership[pair.right]
    )
    return Solution(tuple(rebuilt), meetings=kept)


def fresh_id(solution: Solution, prefix: str) -> str:
    """Choose an unused stable occurrence ID within the solution."""
    used = {visit.id for route in solution.routes for visit in route}
    index = 0
    while f"{prefix}:{index}" in used:
        index += 1
    return f"{prefix}:{index}"


def edited(solution: Solution, agent: int, route: tuple[Visit, ...]) -> Solution:
    """Replace one agent route and preserve valid meeting references."""
    routes = list(solution.routes)
    routes[agent] = tuple(route)
    return normalize(routes, solution.meetings)


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


def unreached_tasks(solution: Solution, problem: object) -> tuple:
    """Return tasks absent from the team's explicit visits, eq. (7)."""
    reached = reached_task_ids(solution)
    return tuple(task for task in problem.tasks if task.id not in reached)
