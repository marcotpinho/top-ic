"""Continuous range contacts between quadratic motion pieces.

Time is scaled to [0,1]. Derivative roots partition a polynomial into
monotone intervals; bracketing finds crossings and critical points expose
isolated tangencies. Positive near-zero critical residuals are unresolved,
not manufactured links. No sampling grid certifies contact continuity.
"""

import math
from functools import lru_cache

import numpy as np
from scipy.optimize import brentq

from .trajectory import AgentTrajectory, MotionPiece

Interval = tuple[float, float]

ROOT_TOL = 2e-13
RESIDUAL_TOL = 2e-11


class ContactUncertain(ValueError):
    """Floating-point signs cannot be classified safely under the policy."""


def _value(coefficients, x):
    return np.polynomial.polynomial.polyval(
        np.longdouble(x), np.array(coefficients, dtype=np.longdouble)
    )


def polynomial_roots(
    coefficients: list[float] | np.ndarray, check_uncertain: bool = True
) -> list[float]:
    """All real roots on [0,1], including derivative-root tangencies."""
    coefficients = list(coefficients)
    while len(coefficients) > 1 and coefficients[-1] == 0:
        coefficients.pop()
    if len(coefficients) == 1:
        return []
    if len(coefficients) == 2:
        root = -coefficients[0] / coefficients[1]
        return [float(root)] if 0 <= root <= 1 else []
    critical = polynomial_roots([i * c for i, c in enumerate(coefficients)][1:], False)
    nodes = sorted(set([0.0, 1.0, *critical]))
    roots = []
    for t in nodes:
        value = _value(coefficients, t)
        if value == 0:
            roots.append(t)
        elif t in critical and abs(value) < RESIDUAL_TOL:
            # A near tangent can hide two crossings: classify as uncertain.
            if check_uncertain:
                raise ContactUncertain("Near-multiple polynomial root is unresolved")
            roots.append(t)
    for left, right in zip(nodes, nodes[1:]):
        fl, fr = _value(coefficients, left), _value(coefficients, right)
        if fl * fr < 0:
            root = brentq(
                lambda x: float(_value(coefficients, x)),
                left,
                right,
                xtol=ROOT_TOL,
                rtol=1e-14,
            )
            roots.append(root)
    return sorted(set(roots))


def range_intervals(
    position: tuple[float, float],
    velocity: tuple[float, float],
    acceleration: tuple[float, float],
    duration: float,
    radius: float,
) -> tuple[Interval, ...]:
    """Relative motion -> local closed contact intervals in seconds."""
    if not math.isfinite(duration) or duration < 0 or radius <= 0:
        raise ValueError("Invalid contact duration/range")
    if duration == 0:
        return ((0.0, 0.0),) if sum(x * x for x in position) <= radius * radius else ()
    q = [
        np.array(
            [position[d], velocity[d] * duration, 0.5 * acceleration[d] * duration**2],
            dtype=np.longdouble,
        )
        for d in range(2)
    ]
    c = np.zeros(5, dtype=np.longdouble)
    for axis in q:
        c += np.convolve(axis, axis)
    c[0] -= np.longdouble(radius) ** 2
    if not np.isfinite(c).all():
        raise ContactUncertain("Nonfinite contact polynomial")
    scale = max(float(np.max(np.abs(c))), 1.0)
    c = c / scale
    if all(x == 0 for x in c):
        return ((0.0, duration),)
    roots = polynomial_roots(c)
    for root in roots:
        if abs(_value(c, root)) > RESIDUAL_TOL:
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
    nodes = sorted(set([0.0, 1.0, *roots]))
    intervals = []
    for left, right in zip(nodes, nodes[1:]):
        if _value(c, (left + right) / 2) < 0:
            intervals.append((left * duration, right * duration))
    for root in roots:
        if not any(
            left - ROOT_TOL <= root * duration <= end + ROOT_TOL
            for left, end in intervals
        ):
            intervals.append((root * duration, root * duration))
    for endpoint in (0.0, 1.0):
        if _value(c, endpoint) <= 0 and not any(
            left <= endpoint * duration <= end for left, end in intervals
        ):
            intervals.append((endpoint * duration, endpoint * duration))
    return merge_intervals(intervals)


def merge_intervals(
    intervals: list[Interval] | tuple[Interval, ...],
) -> tuple[Interval, ...]:
    """Only overlap/shared endpoints merge; never bridge a small proven gap."""
    merged = []
    for start, end in sorted(intervals):
        if start > end:
            raise ValueError("Reversed interval")
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((float(start), float(end)))
    return tuple(merged)


def trajectory_pieces(trajectory: AgentTrajectory, horizon: float) -> list[MotionPiece]:
    pieces = list(trajectory.pieces)
    if horizon > trajectory.completion_time:
        pieces.append(
            MotionPiece(
                trajectory.end.position,
                (0.0, 0.0),
                (0.0, 0.0),
                horizon - trajectory.completion_time,
                trajectory.completion_time,
            )
        )
    return pieces


@lru_cache(maxsize=10000)
def pair_contacts(
    first: AgentTrajectory, second: AgentTrajectory, horizon: float, radius: float
) -> tuple[Interval, ...]:
    a, b = trajectory_pieces(first, horizon), trajectory_pieces(second, horizon)
    if horizon == 0:
        return (
            ((0.0, 0.0),)
            if sum(
                (x - y) ** 2
                for x, y in zip(first.start.position, second.start.position)
            )
            <= radius**2
            else ()
        )
    i = j = 0
    intervals = []
    while i < len(a) and j < len(b):
        left = max(a[i].start_time, b[j].start_time)
        ea = a[i].start_time + a[i].duration
        eb = b[j].start_time + b[j].duration
        right = min(ea, eb)
        if right >= left:
            sa = a[i].state(max(0.0, left - a[i].start_time))
            sb = b[j].state(max(0.0, left - b[j].start_time))
            local = range_intervals(
                tuple(x - y for x, y in zip(sa.position, sb.position)),
                tuple(x - y for x, y in zip(sa.velocity, sb.velocity)),
                tuple(x - y for x, y in zip(a[i].acceleration, b[j].acceleration)),
                right - left,
                radius,
            )
            intervals.extend((left + s, left + e) for s, e in local)
        if ea <= eb:
            i += 1
        if eb <= ea:
            j += 1
    return merge_intervals(intervals)


def effective_intervals(
    raw: tuple[Interval, ...], handshake: float
) -> tuple[Interval, ...]:
    if not math.isfinite(handshake) or handshake < 0:
        raise ValueError("Invalid handshake")
    effective = []
    for start, end in raw:
        if start == 0:
            effective.append((start, end))
        elif end - start >= handshake:
            effective.append((start + handshake, end))
    return tuple(effective)
