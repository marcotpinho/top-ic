"""Least stopped-rendezvous schedule over fixed kinematic connection times."""

from .config import Problem
from .solution import Meeting, Visit
from .trajectory import State, connect


class ScheduleError(ValueError):
    """A meeting schedule violates the occurrence or timing invariants."""


def _indices(routes: tuple[tuple[Visit, ...], ...]) -> tuple[list[int], int]:
    """Allocate arrival/departure nodes for each visit in eqs. (2), (16)."""
    offsets = []
    node_count = 1
    for route in routes:
        offsets.append(node_count)
        node_count += 2 * len(route)
    return offsets, node_count


def _route_edges(
    routes: tuple[tuple[Visit, ...], ...], problem: Problem, offsets: list[int]
) -> tuple[list[tuple[int, int, float]], dict, tuple]:
    """Encode wait and fixed connector durations as difference constraints."""
    edges = []
    visits = {}
    durations = []
    for agent, route in enumerate(routes):
        offset = offsets[agent]
        edges.append((0, offset, 0.0))
        connection_times = []
        for visit_index, visit in enumerate(route):
            if visit.id in visits:
                raise ScheduleError("Duplicate visit ID")
            visits[visit.id] = (agent, visit_index, visit)
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
    return edges, visits, tuple(durations)


def _meeting_edges(
    meetings: tuple[Meeting, ...],
    visits: dict,
    offsets: list[int],
    handshake: float,
    radius: float,
) -> list[tuple[int, int, float]]:
    """Require stopped cross-agent overlap for eq. (16)."""
    edges = []
    for meeting in meetings:
        if meeting.left not in visits or meeting.right not in visits:
            raise ScheduleError("Dangling meeting reference")
        agent, visit_index, left = visits[meeting.left]
        other_agent, other_index, right = visits[meeting.right]
        if (
            agent == other_agent
            or left.kind == "END"
            or right.kind == "END"
            or left.velocity != (0.0, 0.0)
            or right.velocity != (0.0, 0.0)
        ):
            raise ScheduleError(
                "Meeting requires stopped nonterminal visits of distinct agents"
            )
        if sum((x - y) ** 2 for x, y in zip(left.position, right.position)) > radius**2:
            raise ScheduleError("Planned meeting positions outside range")
        left_arrival = offsets[agent] + 2 * visit_index
        right_arrival = offsets[other_agent] + 2 * other_index
        left_departure = left_arrival + 1
        right_departure = right_arrival + 1
        edges.extend(
            (
                (left_arrival, left_departure, handshake),
                (right_arrival, right_departure, handshake),
                (left_arrival, right_departure, handshake),
                (right_arrival, left_departure, handshake),
            )
        )
    return edges


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
    meetings: tuple[Meeting, ...],
    problem: Problem,
    handshake: float,
    radius: float,
    tolerance: float = 1e-8,
) -> tuple[tuple, tuple]:
    """Return least visit times and durations; preserves eqs. (2), (16)."""
    offsets, node_count = _indices(routes)
    edges, visits, durations = _route_edges(routes, problem, offsets)
    edges.extend(_meeting_edges(meetings, visits, offsets, handshake, radius))
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
