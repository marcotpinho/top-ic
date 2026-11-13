"""Derive interior visit headings from route geometry."""

from dataclasses import replace
from math import hypot, sqrt

from ..config import MotionLimits, Problem, Vector
from ..solution import Solution, Visit


def _unit(vector: Vector) -> Vector | None:
    length = hypot(*vector)
    if length <= 1e-12:
        return None
    return (vector[0] / length, vector[1] / length)


def _difference(first: Vector, second: Vector) -> Vector:
    return (first[0] - second[0], first[1] - second[1])


def _speed_fraction(velocity: Vector, limits: MotionLimits) -> float:
    return min(
        1.0,
        max(
            0.1,
            max(abs(value) / bound for value, bound in zip(velocity, limits.velocity)),
        ),
    )


def geometric_velocity(
    route: tuple[Visit, ...] | list[Visit],
    index: int,
    limits: MotionLimits,
    fraction: float,
) -> Vector:
    previous = route[index - 1].position
    current = route[index].position
    following = route[index + 1].position
    incoming = _unit(_difference(current, previous))
    outgoing = _unit(_difference(following, current))
    tangent = _unit(_difference(following, previous))
    if tangent is None:
        tangent = outgoing or incoming or _unit(route[index].velocity) or (1.0, 0.0)
    if incoming is not None and outgoing is not None:
        cosine = max(-1.0, min(1.0, sum(a * b for a, b in zip(incoming, outgoing))))
        fraction = min(fraction, max(0.1, sqrt(max(0.0, (1.0 + cosine) / 2.0))))
    maximum = min(
        bound / abs(component)
        for component, bound in zip(tangent, limits.velocity)
        if abs(component) > 1e-12
    )
    return tuple(
        0.0 if abs(component) < 1e-12 else round(fraction * maximum * component, 12)
        for component in tangent
    )


def align_headings(solution: Solution, problem: Problem) -> Solution:
    routes = []
    changed = False
    for agent, source in enumerate(solution.routes):
        route = list(source)
        for index in range(1, len(route) - 1):
            velocity = geometric_velocity(
                route,
                index,
                problem.limits[agent],
                _speed_fraction(route[index].velocity, problem.limits[agent]),
            )
            if velocity != route[index].velocity:
                route[index] = replace(route[index], velocity=velocity)
                changed = True
        routes.append(tuple(route))
    return Solution(tuple(routes)) if changed else solution
