"""Least route schedule over fixed kinematic connection times."""

from ..config import Problem
from ..solution import Visit
from .trajectory import State, connect


class ScheduleError(ValueError):
    """A route schedule violates the occurrence or timing invariants."""


def _indices(routes: tuple[tuple[Visit, ...], ...]) -> tuple[list[int], int]:
    """Allocate arrival/departure nodes for each visit in eq. (2)."""
    offsets = []
    node_count = 1
    for route in routes:
        offsets.append(node_count)
        node_count += 2 * len(route)
    return offsets, node_count


def _route_edges(
    routes: tuple[tuple[Visit, ...], ...], problem: Problem, offsets: list[int]
) -> tuple[list[tuple[int, int, float]], tuple]:
    """Encode wait and fixed connector durations as difference constraints."""
    edges = []
    durations = []
    identities = set()
    for agent, route in enumerate(routes):
        offset = offsets[agent]
        edges.append((0, offset, 0.0))
        connection_times = []
        for visit_index, visit in enumerate(route):
            if visit.id in identities:
                raise ScheduleError("Duplicate visit ID")
            identities.add(visit.id)
            edges.append(
                (offset + 2 * visit_index, offset + 2 * visit_index + 1, visit.wait)
            )
        for visit_index, (start, end) in enumerate(zip(route, route[1:])):
            duration = connect(
                State(start.position, start.velocity),
                State(end.position, end.velocity),
                problem.limits[agent],
            ).duration
            connection_times.append(duration)
            departure = offset + 2 * visit_index + 1
            arrival = offset + 2 * (visit_index + 1)
            edges.extend(
                ((departure, arrival, duration), (arrival, departure, -duration))
            )
        durations.append(tuple(connection_times))
    return edges, tuple(durations)


def _longest_paths(node_count: int, edges: list[tuple[int, int, float]]) -> list[float]:
    """Find the least nonnegative schedule or reject a positive cycle."""
    values = [0.0] * node_count
    for _ in range(node_count):
        changed = False
        for source, destination, weight in edges:
            proposed = values[source] + weight
            if proposed > values[destination]:
                values[destination] = proposed
                changed = True
        if not changed:
            return values
    raise ScheduleError("Positive-cycle rendezvous deadlock")


def schedule(
    routes: tuple[tuple[Visit, ...], ...],
    problem: Problem,
    tolerance: float = 1e-8,
) -> tuple[tuple, tuple]:
    """Return least visit times and durations; implements eq. (2)."""
    offsets, node_count = _indices(routes)
    edges, durations = _route_edges(routes, problem, offsets)
    values = _longest_paths(node_count, edges)
    timing = []
    for agent, route in enumerate(routes):
        pairs = tuple(
            (
                values[offsets[agent] + 2 * visit_index],
                values[offsets[agent] + 2 * visit_index + 1],
            )
            for visit_index in range(len(route))
        )
        if pairs[0][0] != 0 or abs(pairs[-1][1] - pairs[-1][0]) > tolerance:
            raise ScheduleError("Invalid pinned/terminal time")
        timing.append(pairs)
    return tuple(timing), durations
