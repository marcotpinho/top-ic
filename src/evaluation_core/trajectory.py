"""Deterministic time-optimal box-bounded double-integrator connections.

For fixed duration T, every admissible scalar velocity lies between the
Lipschitz envelopes max(-V,v0-A*t,v1-A*(T-t)) and
min(V,v0+A*t,v1+A*(T-t)). Their integrals bound reachable displacement.
Convex interpolation realizes every intermediate displacement. The earliest
common feasible duration is among roots of piecewise-quadratic envelope
integrals and domain boundaries. This explicitly handles disconnected sets
of feasible durations (unlike max(independent axis minimum)).
"""

from dataclasses import dataclass
from functools import lru_cache
from math import isfinite, sqrt

from ..config import MotionLimits, Vector, vector

VERSION = "kop-patterns-1-geometric-heading"
TOL = 1e-8


class MotionError(ValueError):
    pass


@dataclass(frozen=True)
class State:
    position: Vector
    velocity: Vector = (0.0, 0.0)

    def __post_init__(self):
        object.__setattr__(self, "position", vector(self.position))
        object.__setattr__(self, "velocity", vector(self.velocity))


@dataclass(frozen=True)
class MotionPiece:
    position: Vector
    velocity: Vector
    acceleration: Vector
    duration: float
    start_time: float = 0.0

    def state(self, t: float) -> State:
        return State(
            (
                self.position[0]
                + self.velocity[0] * t
                + 0.5 * self.acceleration[0] * t * t,
                self.position[1]
                + self.velocity[1] * t
                + 0.5 * self.acceleration[1] * t * t,
            ),
            (
                self.velocity[0] + self.acceleration[0] * t,
                self.velocity[1] + self.acceleration[1] * t,
            ),
        )


@dataclass(frozen=True)
class Connection:
    pieces: tuple[MotionPiece, ...]
    duration: float


@dataclass(frozen=True)
class AgentTrajectory:
    pieces: tuple[MotionPiece, ...]
    completion_time: float
    start: State
    end: State

    def state(self, t: float) -> State:
        if t < 0:
            raise ValueError("Time must be nonnegative")
        if t > self.completion_time:
            return State(self.end.position, (0.0, 0.0))
        if t == self.completion_time:
            return self.end
        for piece in self.pieces:
            if piece.start_time <= t <= piece.start_time + piece.duration + TOL:
                return piece.state(min(piece.duration, max(0.0, t - piece.start_time)))
        return self.start


def _bounds(T, v0, v1, V, A):
    dv = v1 - v0
    upper = (
        (v0 + v1) * T / 2 + A * T * T / 4 - dv * dv / (4 * A)
        if T <= (2 * V - v0 - v1) / A
        else V * T - ((V - v0) ** 2 + (V - v1) ** 2) / (2 * A)
    )
    lower = (
        (v0 + v1) * T / 2 - A * T * T / 4 + dv * dv / (4 * A)
        if T <= (2 * V + v0 + v1) / A
        else -V * T + ((V + v0) ** 2 + (V + v1) ** 2) / (2 * A)
    )
    return lower, upper


def _roots(a, b, c):
    if abs(a) < 1e-14:
        return [] if abs(b) < 1e-14 else [-c / b]
    discriminant = b * b - 4 * a * c
    if discriminant < -1e-10:
        return []
    r = sqrt(max(0.0, discriminant))
    return [(-b - r) / (2 * a), (-b + r) / (2 * a)]


def _candidates(x, v0, v1, V, A):
    dv = v1 - v0
    return [
        abs(dv) / A,
        (2 * V - v0 - v1) / A,
        (2 * V + v0 + v1) / A,
        (x + ((V - v0) ** 2 + (V - v1) ** 2) / (2 * A)) / V,
        (((V + v0) ** 2 + (V + v1) ** 2) / (2 * A) - x) / V,
        *_roots(A / 4, (v0 + v1) / 2, -dv * dv / (4 * A) - x),
        *_roots(-A / 4, (v0 + v1) / 2, dv * dv / (4 * A) - x),
    ]


def _axis_profile(T, x, v0, v1, V, A):
    lower, upper = _bounds(T, v0, v1, V, A)
    ratio = 0.5 if abs(upper - lower) < 1e-12 else (x - lower) / (upper - lower)
    if not -TOL <= ratio <= 1 + TOL:
        raise MotionError("Unresolved envelope interpolation")
    ratio = min(1.0, max(0.0, ratio))
    # All intersections of the three affine envelopes are safe breakpoints;
    # extra inactive intersections only subdivide constant acceleration.
    times = {0.0, T}
    for sign in (1.0, -1.0):
        lines = [(sign * V, 0.0), (v0, sign * A), (v1 + sign * A * T, -sign * A)]
        for i in range(3):
            for j in range(i):
                if lines[i][1] != lines[j][1]:
                    t = (lines[j][0] - lines[i][0]) / (lines[i][1] - lines[j][1])
                    if 1e-12 < t < T - 1e-12:
                        times.add(t)

    def speed(t):
        lo = max(-V, v0 - A * t, v1 - A * (T - t))
        hi = min(V, v0 + A * t, v1 + A * (T - t))
        return (1 - ratio) * lo + ratio * hi

    times = sorted(times)
    return times, [speed(t) for t in times]


def _integrate_axis(v0, phases):
    position = 0.0
    velocity = v0
    for duration, acceleration in phases:
        position += velocity * duration + 0.5 * acceleration * duration * duration
        velocity += acceleration * duration
    return position, velocity


def _valid_axis_pattern(phases, T, x, v0, v1, V, A):
    if any(duration < -1e-9 for duration, _ in phases):
        return None
    normalized = tuple(
        (max(0.0, duration), acceleration)
        for duration, acceleration in phases
        if duration > 1e-12
    )
    if abs(sum(duration for duration, _ in normalized) - T) > 2e-7:
        return None
    velocity = v0
    for duration, acceleration in normalized:
        if abs(acceleration) > A + 1e-9:
            return None
        tail = velocity + acceleration * duration
        if max(abs(velocity), abs(tail)) > V + 2e-7:
            return None
        velocity = tail
    displacement, velocity = _integrate_axis(v0, normalized)
    if abs(displacement - x) > 2e-7 or abs(velocity - v1) > 2e-7:
        return None
    return normalized


def _classical_patterns(T, x, v0, v1, V, A):
    delta = v1 - v0
    for acceleration in (A, -A):
        discriminant = (
            acceleration * acceleration * T * T
            + 2 * (v1 + v0) * acceleration * T
            - 4 * acceleration * x
            - delta * delta
        )
        if discriminant < -1e-9:
            continue
        root = sqrt(max(0.0, discriminant))
        for branch in (-1.0, 1.0):
            t1 = (acceleration * T + delta + branch * root) / (
                2 * acceleration
            )
            t2 = -branch * root / acceleration
            t3 = (acceleration * T - delta + branch * root) / (
                2 * acceleration
            )
            pattern = _valid_axis_pattern(
                (
                    (t1, acceleration),
                    (t2, 0.0),
                    (t3, -acceleration),
                ),
                T,
                x,
                v0,
                v1,
                V,
                A,
            )
            if pattern is not None:
                yield pattern


def _synchronization_patterns(T, x, v0, v1, V, A):
    delta = v1 - v0
    for acceleration in (A, -A):
        accelerated_time = delta / acceleration
        t2 = T - accelerated_time
        if accelerated_time < -1e-9 or t2 < -1e-9:
            continue
        if abs(t2) <= 1e-12:
            if abs(x - (v0 * T + 0.5 * acceleration * T * T)) > 2e-7:
                continue
            t1 = 0.0
        else:
            t1 = (
                x
                - v0 * T
                - 0.5 * acceleration * accelerated_time * accelerated_time
            ) / (acceleration * t2)
        t3 = accelerated_time - t1
        pattern = _valid_axis_pattern(
            (
                (t1, acceleration),
                (t2, 0.0),
                (t3, acceleration),
            ),
            T,
            x,
            v0,
            v1,
            V,
            A,
        )
        if pattern is not None:
            yield pattern


def _axis_pattern(T, x, v0, v1, V, A):
    return next(
        iter(
            (
                *_classical_patterns(T, x, v0, v1, V, A),
                *_synchronization_patterns(T, x, v0, v1, V, A),
            )
        ),
        None,
    )


def _pattern_acceleration(pattern, t):
    elapsed = 0.0
    for duration, acceleration in pattern:
        if t <= elapsed + duration + 1e-12:
            return acceleration
        elapsed += duration
    return pattern[-1][1]


@lru_cache(maxsize=50000)
def connect(start: State, end: State, limits: MotionLimits) -> Connection:
    for vel in (start.velocity, end.velocity):
        if vel == (0.0, 0.0):
            raise MotionError("Boundary velocity must be nonzero")
        if any(abs(v) > V + 1e-10 for v, V in zip(vel, limits.velocity)):
            raise MotionError("Boundary velocity outside limits")
    if start == end:
        return Connection((), 0.0)
    axes = [
        (
            end.position[d] - start.position[d],
            start.velocity[d],
            end.velocity[d],
            limits.velocity[d],
            limits.acceleration[d],
        )
        for d in range(2)
    ]
    candidates = sorted(
        set(
            [
                0.0,
                *(t for ax in axes for t in _candidates(*ax) if isfinite(t) and t >= 0),
            ]
        )
    )
    duration = None
    patterns = None
    for t in candidates:
        candidate_patterns = tuple(_axis_pattern(t, *axis) for axis in axes)
        if all(pattern is not None for pattern in candidate_patterns):
            duration = t
            patterns = candidate_patterns
            break
    if duration is None or duration < 1e-12 or patterns is None:
        raise MotionError("No numerically resolved common duration")
    times = {0.0, duration}
    for pattern in patterns:
        elapsed = 0.0
        for phase_duration, _ in pattern:
            elapsed += phase_duration
            if 1e-12 < elapsed < duration - 1e-12:
                times.add(elapsed)
    times = sorted(times)

    state = start
    pieces = []
    for t0, t1 in zip(times, times[1:]):
        h = t1 - t0
        if h < 1e-12:
            continue
        midpoint = (t0 + t1) / 2
        a = tuple(_pattern_acceleration(patterns[d], midpoint) for d in range(2))
        piece = MotionPiece(state.position, state.velocity, a, h, t0)
        pieces.append(piece)
        state = piece.state(h)
    result = Connection(tuple(pieces), duration)
    validate_connection(result, start, end, limits)
    return result


def validate_connection(
    connection: Connection,
    start: State,
    end: State,
    limits: MotionLimits,
    tolerance: float = 2e-7,
) -> None | bool:
    if start.velocity == (0.0, 0.0) or end.velocity == (0.0, 0.0):
        raise MotionError("Boundary velocity must be nonzero")
    state = start
    elapsed = 0.0
    for piece in connection.pieces:
        if piece.duration <= 0 or not isfinite(piece.duration):
            raise MotionError("Invalid motion duration")
        if (
            max(
                abs(a - b)
                for a, b in zip(
                    state.position + state.velocity, piece.position + piece.velocity
                )
            )
            > tolerance
        ):
            raise MotionError("Discontinuous motion")
        if abs(piece.start_time - elapsed) > tolerance:
            raise MotionError("Discontinuous time")
        tail = piece.state(piece.duration)
        for d in range(2):
            if (
                max(abs(piece.velocity[d]), abs(tail.velocity[d]))
                > limits.velocity[d] + tolerance
                or abs(piece.acceleration[d]) > limits.acceleration[d] + tolerance
            ):
                raise MotionError("Continuous motion bound violated")
        state = tail
        elapsed += piece.duration
    if (
        abs(elapsed - connection.duration) > tolerance
        or max(
            abs(a - b)
            for a, b in zip(
                state.position + state.velocity, end.position + end.velocity
            )
        )
        > tolerance
    ):
        raise MotionError("Endpoint/duration residual exceeds tolerance")
    return True
