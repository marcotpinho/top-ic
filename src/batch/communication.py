"""Vectorized chronological communication sweeps over candidate batches."""

from dataclasses import dataclass
from time import perf_counter

import numpy as np

from ..evaluation_core.communication import CommunicationResult
from .contacts import ContactBatch
from .tensors import TrajectoryBatch


@dataclass(frozen=True)
class SweepBatch:
    results: tuple[CommunicationResult | None, ...]
    peaks: np.ndarray
    violation: np.ndarray
    delta: np.ndarray
    integrated_excess: np.ndarray
    status: np.ndarray


def _closure(adjacency: np.ndarray) -> np.ndarray:
    _, agents, _ = adjacency.shape
    reachable = adjacency.copy()
    reachable |= np.eye(agents, dtype=bool)[None, :, :]
    steps = max(1, int(np.ceil(np.log2(max(agents, 1)))))
    for _ in range(steps):
        reachable |= np.einsum(
            "bij,bjk->bik",
            reachable.astype(np.int8),
            reachable.astype(np.int8),
            optimize=True,
        ).astype(bool)
    return reachable


def _propagate(clock: np.ndarray, time: np.ndarray, adjacency: np.ndarray, active):
    if not np.any(active):
        return
    indices = np.flatnonzero(active)
    selected = clock[indices].copy()
    agents = selected.shape[1]
    diagonal = np.arange(agents)
    selected[:, diagonal, diagonal] = time[indices, None]
    reachable = _closure(adjacency[indices])
    expanded = np.where(reachable[:, :, :, None], selected[:, None, :, :], -np.inf)
    clock[indices] = np.max(expanded, axis=2)


def _adjacency(
    contacts: ContactBatch, times: np.ndarray, agents: int, open_interval=False
):
    batch = contacts.intervals.shape[0]
    adjacency = np.zeros((batch, agents, agents), dtype=bool)
    for pair_index, (first, second) in enumerate(contacts.pair_agents):
        intervals = contacts.intervals[:, pair_index]
        starts = intervals[:, :, 0]
        ends = intervals[:, :, 1]
        finite = np.isfinite(starts)
        if open_interval:
            present = np.any(
                finite & (starts < times[:, None]) & (times[:, None] < ends), axis=1
            )
        else:
            present = np.any(
                finite & (starts <= times[:, None]) & (times[:, None] <= ends), axis=1
            )
        adjacency[:, first, second] = present
        adjacency[:, second, first] = present
    return adjacency


def batch_sweep(
    trajectories: TrajectoryBatch,
    contacts: ContactBatch,
    recurrence_bound: float,
) -> SweepBatch:
    batch = trajectories.size
    agents = trajectories.comp.shape[1]
    horizons = np.max(trajectories.comp, axis=1)
    event_rows = []
    for batch_index in range(batch):
        values = {0.0, float(horizons[batch_index])}
        for pair_index in range(len(contacts.pair_agents)):
            count = int(contacts.counts[batch_index, pair_index])
            for start, end in contacts.intervals[batch_index, pair_index, :count]:
                values.add(float(start))
                values.add(float(end))
        event_rows.append(np.asarray(sorted(values), dtype=np.float64))
    event_count = np.asarray([len(row) for row in event_rows], dtype=np.int16)
    max_events = max(event_count, default=1)
    events = np.repeat(horizons[:, None], max_events, axis=1)
    for batch_index, row in enumerate(event_rows):
        events[batch_index, : len(row)] = row
    clock = np.zeros((batch, agents, agents), dtype=np.float64)
    peaks = np.zeros_like(clock)
    delta = np.zeros(batch, dtype=np.float64)
    integrated = np.zeros(batch, dtype=np.float64)
    previous = np.zeros(batch, dtype=np.float64)
    previous_ages = np.zeros_like(clock)
    off_diagonal = ~np.eye(agents, dtype=bool)
    bottleneck = [None] * batch
    histories = [[] for _ in range(batch)]
    for event_index in range(max_events):
        active = event_index < event_count
        time = events[:, event_index]
        advanced = active & (time > previous)
        middle = (previous + time) / 2
        open_adjacency = _adjacency(contacts, middle, agents, True)
        _propagate(clock, time, open_adjacency, advanced)
        left_ages = np.where(off_diagonal[None, :, :], time[:, None, None] - clock, 0.0)
        if np.any(advanced):
            start = previous_ages - recurrence_bound
            end = left_ages - recurrence_bound
            duration = time - previous
            both = (start > 0) & (end > 0) & off_diagonal[None, :, :]
            rising = (start <= 0) & (end > 0) & off_diagonal[None, :, :]
            falling = (start > 0) & (end <= 0) & off_diagonal[None, :, :]
            areas = np.zeros_like(clock)
            areas[both] = ((start + end) * duration[:, None, None] / 2)[both]
            rising_denominator = 2 * (end - start)
            falling_denominator = 2 * (start - end)
            np.divide(
                end**2 * duration[:, None, None],
                rising_denominator,
                out=areas,
                where=rising,
            )
            falling_area = np.zeros_like(clock)
            np.divide(
                start**2 * duration[:, None, None],
                falling_denominator,
                out=falling_area,
                where=falling,
            )
            areas[falling] = falling_area[falling]
            integrated += np.where(advanced, np.sum(areas, axis=(1, 2)), 0.0)
        left_masked = np.where(off_diagonal[None, :, :], left_ages, -np.inf)
        left_values = (
            np.max(left_masked, axis=(1, 2)) if agents > 1 else np.zeros(batch)
        )
        np.maximum(peaks, left_ages, out=peaks)
        improved = active & (left_values > delta)
        for batch_index in np.flatnonzero(improved):
            receiver, source = np.unravel_index(
                np.argmax(left_masked[batch_index]), (agents, agents)
            )
            bottleneck[batch_index] = (
                int(source),
                int(receiver),
                float(time[batch_index]),
                "left",
            )
        delta = np.where(improved, left_values, delta)
        event_adjacency = _adjacency(contacts, time, agents, False)
        _propagate(clock, time, event_adjacency, active)
        exact_ages = np.where(
            off_diagonal[None, :, :], time[:, None, None] - clock, 0.0
        )
        exact_masked = np.where(off_diagonal[None, :, :], exact_ages, -np.inf)
        exact_values = (
            np.max(exact_masked, axis=(1, 2)) if agents > 1 else np.zeros(batch)
        )
        np.maximum(peaks, exact_ages, out=peaks)
        improved = active & (exact_values > delta)
        for batch_index in np.flatnonzero(improved):
            receiver, source = np.unravel_index(
                np.argmax(exact_masked[batch_index]), (agents, agents)
            )
            bottleneck[batch_index] = (
                int(source),
                int(receiver),
                float(time[batch_index]),
                "event",
            )
        delta = np.where(improved, exact_values, delta)
        for batch_index in np.flatnonzero(active):
            histories[batch_index].append(
                (
                    float(time[batch_index]),
                    float(left_values[batch_index]),
                    float(exact_values[batch_index]),
                )
            )
        previous = np.where(active, time, previous)
        previous_ages = np.where(active[:, None, None], exact_ages, previous_ages)
    diagonal = np.eye(agents, dtype=bool)[None, :, :]
    violation = np.sum(
        np.where(diagonal, 0.0, np.maximum(0.0, peaks - recurrence_bound)),
        axis=(1, 2),
    )
    results = []
    for batch_index in range(batch):
        if contacts.status[batch_index]:
            results.append(None)
            continue
        results.append(
            CommunicationResult(
                float(delta[batch_index]),
                contacts.records[batch_index],
                tuple(histories[batch_index]),
                tuple(
                    tuple(float(value) for value in row) for row in clock[batch_index]
                ),
                bottleneck[batch_index],
                pair_peaks=tuple(
                    tuple(float(value) for value in row) for row in peaks[batch_index]
                ),
                integrated_excess=float(integrated[batch_index]),
            )
        )
    return SweepBatch(
        tuple(results), peaks, violation, delta, integrated, contacts.status.copy()
    )


def batch_evaluate_communication(
    trajectories: TrajectoryBatch,
    rssi_threshold: float,
    recurrence_bound: float,
    metrics=None,
) -> SweepBatch:
    from .contacts import batch_pair_contacts

    started = perf_counter()
    contacts = batch_pair_contacts(trajectories, rssi_threshold)
    if metrics is not None:
        metrics["contact_seconds"] += perf_counter() - started
    started = perf_counter()
    result = batch_sweep(trajectories, contacts, recurrence_bound)
    if metrics is not None:
        metrics["sweep_seconds"] += perf_counter() - started
    return result
