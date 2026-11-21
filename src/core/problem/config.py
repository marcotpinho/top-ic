from math import atan2, cos, isfinite, pi, sin

Vector = tuple[float, float]


def vector(value) -> Vector:
    if len(value) != 2 or not all(isfinite(float(x)) for x in value):
        raise ValueError("Expected a finite 2D vector")
    return tuple(float(x) for x in value)


def moving_velocity(limits, start: Vector, end: Vector) -> Vector:
    angle = round(atan2(end[1] - start[1], end[0] - start[0]) / (pi / 4)) * (pi / 4)
    direction = (cos(angle), sin(angle))
    maximum = min(
        limits.velocity[d] / abs(direction[d])
        for d in range(2)
        if abs(direction[d]) > 1e-12
    )
    return tuple(0.0 if abs(v) < 1e-12 else 0.1 * maximum * v for v in direction)


def velocity_menu(limits, config):
    states = set()
    for h in range(config.headings):
        direction = (
            cos(2 * pi * h / config.headings),
            sin(2 * pi * h / config.headings),
        )
        maximum = min(
            limits.velocity[d] / abs(direction[d])
            for d in range(2)
            if abs(direction[d]) > 1e-12
        )
        for fraction in config.speed_fractions:
            states.add(
                tuple(
                    0.0 if abs(x) < 1e-12 else round(x, 12)
                    for x in (
                        fraction * maximum * direction[0],
                        fraction * maximum * direction[1],
                    )
                )
            )
    return tuple(sorted(states))
