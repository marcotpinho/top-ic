"""Route timing from consecutive kinematic connections without pauses."""

from itertools import pairwise

from ..config import Problem
from ..solution import Visit
from .trajectory import State, connect


def schedule(
    routes: tuple[tuple[Visit, ...], ...],
    problem: Problem,
) -> tuple[tuple, tuple]:
    """Return coincident arrival/departure times and connection durations."""
    timing = []
    durations = []
    for agent, route in enumerate(routes):
        elapsed = 0.0
        pairs = [(elapsed, elapsed)]
        connection_times = []
        for start, end in pairwise(route):
            duration = connect(
                State(start.position, start.velocity),
                State(end.position, end.velocity),
                problem.limits[agent],
            ).duration
            connection_times.append(duration)
            elapsed += duration
            pairs.append((elapsed, elapsed))
        timing.append(tuple(pairs))
        durations.append(tuple(connection_times))
    return tuple(timing), tuple(durations)
