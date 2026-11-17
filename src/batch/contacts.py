"""Batched continuous range contacts for padded trajectory tensors."""

from dataclasses import dataclass
from itertools import pairwise

import numpy as np

from ..evaluation_core.communication import ContactRecord
from ..evaluation_core.contacts import (
    RESIDUAL_TOL,
    ROOT_TOL,
    ContactUncertain,
    _value,
    merge_intervals,
    polynomial_roots,
    trajectory_pieces,
)
from ..evaluation_core.rssi import distance_at_rssi, meets_threshold
from .tensors import TrajectoryBatch


@dataclass(frozen=True)
class ContactBatch:
    intervals: np.ndarray
    counts: np.ndarray
    status: np.ndarray
    pair_agents: tuple[tuple[int, int], ...]
    records: tuple[tuple[ContactRecord, ...], ...]


@dataclass(frozen=True)
class _Segment:
    batch: int
    pair: int
    left: float
    duration: float
    position: tuple[float, float]
    velocity: tuple[float, float]
    acceleration: tuple[float, float]


def _quartics(segments: list[_Segment], radius: float):
    if not segments:
        return np.empty((0, 5)), np.empty((0, 2, 3)), np.empty(0)
    position = np.asarray([segment.position for segment in segments], dtype=np.float64)
    velocity = np.asarray([segment.velocity for segment in segments], dtype=np.float64)
    acceleration = np.asarray(
        [segment.acceleration for segment in segments], dtype=np.float64
    )
    duration = np.asarray([segment.duration for segment in segments], dtype=np.float64)
    q = np.empty((len(segments), 2, 3), dtype=np.float64)
    q[:, :, 0] = position
    q[:, :, 1] = velocity * duration[:, None]
    q[:, :, 2] = 0.5 * acceleration * duration[:, None] ** 2
    coefficients = np.empty((len(segments), 5), dtype=np.float64)
    coefficients[:, 0] = np.sum(q[:, :, 0] ** 2, axis=1) - radius**2
    coefficients[:, 1] = 2 * np.sum(q[:, :, 0] * q[:, :, 1], axis=1)
    coefficients[:, 2] = np.sum(q[:, :, 1] ** 2 + 2 * q[:, :, 0] * q[:, :, 2], axis=1)
    coefficients[:, 3] = 2 * np.sum(q[:, :, 1] * q[:, :, 2], axis=1)
    coefficients[:, 4] = np.sum(q[:, :, 2] ** 2, axis=1)
    scale = np.maximum(np.max(np.abs(coefficients), axis=1), 1.0)
    return coefficients / scale[:, None], q, scale


def _polynomial_intervals(coefficients, q, duration, radius, scale):
    if duration == 0:
        return ((0.0, 0.0),) if np.dot(q[:, 0], q[:, 0]) <= radius**2 else ()
    if not np.isfinite(coefficients).all():
        raise ContactUncertain("Nonfinite contact polynomial")
    if np.all(coefficients == 0):
        return ((0.0, duration),)
    roots = polynomial_roots(coefficients)
    for root in roots:
        if abs(_value(coefficients, root)) > RESIDUAL_TOL:
            raise ContactUncertain("Root residual outside numerical policy")
        relative = np.array(
            [np.polynomial.polynomial.polyval(np.longdouble(root), axis) for axis in q],
            dtype=np.longdouble,
        )
        if (
            abs(np.dot(relative, relative) - np.longdouble(radius) ** 2)
            > scale * RESIDUAL_TOL
        ):
            raise ContactUncertain(
                "Reconstructed range residual outside numerical policy"
            )
    nodes = sorted({0.0, 1.0, *roots})
    intervals = [
        (left * duration, right * duration)
        for left, right in pairwise(nodes)
        if _value(coefficients, (left + right) / 2) < 0
    ]
    for root in roots:
        point = root * duration
        if not any(
            left - ROOT_TOL <= point <= right + ROOT_TOL for left, right in intervals
        ):
            intervals.append((point, point))
    for endpoint in (0.0, 1.0):
        point = endpoint * duration
        if _value(coefficients, endpoint) <= 0 and not any(
            left <= point <= right for left, right in intervals
        ):
            intervals.append((point, point))
    return merge_intervals(intervals)


def batch_pair_contacts(
    trajectories: TrajectoryBatch, rssi_threshold: float
) -> ContactBatch:
    radius = distance_at_rssi(rssi_threshold)
    agents = trajectories.comp.shape[1]
    pairs = tuple((m, n) for m in range(agents) for n in range(m + 1, agents))
    segments: list[_Segment] = []
    pair_intervals = [[[] for _ in pairs] for _ in range(trajectories.size)]
    status = np.zeros(trajectories.size, dtype=np.int8)
    for batch_index, row in enumerate(trajectories.trajectories):
        horizon = float(np.max(trajectories.comp[batch_index]))
        for pair_index, (first_agent, second_agent) in enumerate(pairs):
            first = row[first_agent]
            second = row[second_agent]
            if horizon == 0:
                distance = sum(
                    (x - y) ** 2
                    for x, y in zip(first.start.position, second.start.position)
                )
                if meets_threshold(np.sqrt(distance), rssi_threshold):
                    pair_intervals[batch_index][pair_index].append((0.0, 0.0))
                continue
            first_pieces = trajectory_pieces(first, horizon)
            second_pieces = trajectory_pieces(second, horizon)
            first_index = second_index = 0
            while first_index < len(first_pieces) and second_index < len(second_pieces):
                first_piece = first_pieces[first_index]
                second_piece = second_pieces[second_index]
                left = max(first_piece.start_time, second_piece.start_time)
                first_end = first_piece.start_time + first_piece.duration
                second_end = second_piece.start_time + second_piece.duration
                right = min(first_end, second_end)
                if right < left:
                    if first_end <= second_end:
                        first_index += 1
                    if second_end <= first_end:
                        second_index += 1
                    continue
                first_state = first_piece.state(max(0.0, left - first_piece.start_time))
                second_state = second_piece.state(
                    max(0.0, left - second_piece.start_time)
                )
                segments.append(
                    _Segment(
                        batch_index,
                        pair_index,
                        left,
                        right - left,
                        tuple(
                            x - y
                            for x, y in zip(first_state.position, second_state.position)
                        ),
                        tuple(
                            x - y
                            for x, y in zip(first_state.velocity, second_state.velocity)
                        ),
                        tuple(
                            x - y
                            for x, y in zip(
                                first_piece.acceleration, second_piece.acceleration
                            )
                        ),
                    )
                )
                if first_end <= second_end:
                    first_index += 1
                if second_end <= first_end:
                    second_index += 1
    coefficients, q, scales = _quartics(segments, radius)
    for index, segment in enumerate(segments):
        if status[segment.batch]:
            continue
        try:
            local = _polynomial_intervals(
                coefficients[index],
                q[index],
                segment.duration,
                radius,
                scales[index],
            )
        except ContactUncertain:
            status[segment.batch] = 1
            pair_intervals[segment.batch] = [[] for _ in pairs]
            continue
        pair_intervals[segment.batch][segment.pair].extend(
            (segment.left + start, segment.left + end) for start, end in local
        )
    merged = [
        [merge_intervals(intervals) for intervals in row] for row in pair_intervals
    ]
    max_intervals = max(
        1,
        max(
            (len(intervals) for row in merged for intervals in row),
            default=0,
        ),
    )
    tensor = np.full(
        (trajectories.size, len(pairs), max_intervals, 2),
        np.nan,
        dtype=np.float64,
    )
    counts = np.zeros((trajectories.size, len(pairs)), dtype=np.int16)
    records = []
    for batch_index, row in enumerate(merged):
        record_row = []
        for pair_index, intervals in enumerate(row):
            counts[batch_index, pair_index] = len(intervals)
            if intervals:
                tensor[batch_index, pair_index, : len(intervals)] = intervals
            record_row.append(ContactRecord(pairs[pair_index], intervals, intervals))
        records.append(tuple(record_row))
    return ContactBatch(tensor, counts, status, pairs, tuple(records))
