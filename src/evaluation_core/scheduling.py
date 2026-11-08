"""Route timing from consecutive kinematic connections without pauses."""

from ..config import Problem
from ..solution import Visit
from .trajectory import State, connect


class ScheduleError(ValueError):
    """A route schedule violates the occurrence or timing invariants."""


def schedule(
    routes: tuple[tuple[Visit, ...], ...],
    problem: Problem,
) -> tuple[tuple, tuple]:
    """Return coincident arrival/departure times and connection durations."""
    timing = []
    durations = []
    identities = set()
    for agent, route in enumerate(routes):
        for visit in route:
            if visit.id in identities:
                raise ScheduleError("Duplicate visit ID")
            identities.add(visit.id)
        elapsed = 0.0
        pairs = [(elapsed, elapsed)]
        connection_times = []
        for start, end in zip(route, route[1:]):
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
