"""Local contact preservation when a budget repair removes a FREE visit."""

from dataclasses import replace
from typing import TYPE_CHECKING

from ..evaluation_core.contacts import (
    merge_intervals,
    range_intervals,
    trajectory_pieces,
)
from ..evaluation_core.trajectory import MotionPiece, State, connect
from ..solution import Solution

if TYPE_CHECKING:
    from .runner import Runner


def _contacts(pieces, other, horizon, radius, start, end):
    intervals = []
    other_pieces = trajectory_pieces(other, horizon)
    for first in pieces:
        if first.start_time > end or first.start_time + first.duration < start:
            continue
        for second in other_pieces:
            left = max(start, first.start_time, second.start_time)
            right = min(
                end,
                first.start_time + first.duration,
                second.start_time + second.duration,
            )
            if right < left:
                continue
            a = first.state(max(0.0, left - first.start_time))
            b = second.state(max(0.0, left - second.start_time))
            local = range_intervals(
                tuple(x - y for x, y in zip(a.position, b.position)),
                tuple(x - y for x, y in zip(a.velocity, b.velocity)),
                tuple(x - y for x, y in zip(first.acceleration, second.acceleration)),
                right - left,
                radius,
            )
            intervals.extend((left + s, left + e) for s, e in local)
    return merge_intervals(intervals)


def preserves_local_contacts(
    runner: "Runner",
    solution: Solution,
    trajectories: tuple,
    agent: int,
    index: int,
    start: float,
    end: float,
) -> bool:
    route = solution.routes[agent]
    before, after = route[index - 1], route[index + 1]
    connection = connect(
        State(before.position, before.velocity),
        State(after.position, after.velocity),
        runner.problem.limits[agent],
    )
    pieces = tuple(
        replace(piece, start_time=start + piece.start_time)
        for piece in connection.pieces
    )
    if not pieces:
        pieces = (
            MotionPiece(before.position, before.velocity, (0.0, 0.0), 0.0, start),
        )
    horizon = max(trajectory.completion_time for trajectory in trajectories)
    tolerance = runner.config.contact_tolerance
    for other_agent, other in enumerate(trajectories):
        if runner.exhausted():
            return False
        if other_agent == agent:
            continue
        old = _contacts(
            trajectories[agent].pieces,
            other,
            horizon,
            runner.config.comm_range,
            start,
            end,
        )
        if not old:
            continue
        new = _contacts(
            pieces,
            other,
            horizon,
            runner.config.comm_range,
            start,
            start + connection.duration,
        )
        if any(
            not any(c <= a + tolerance and d >= b - tolerance for c, d in new)
            for a, b in old
        ):
            return False
    return True
