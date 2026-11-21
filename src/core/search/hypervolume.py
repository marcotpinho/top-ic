"""Exact two-objective hypervolume for normalized minimization points."""

from collections.abc import Iterable


def hypervolume_2d(points: Iterable[tuple[float, float]]) -> float:
    """Measure minimization area against normalized reference (1, 1)."""
    bounded = sorted(
        {
            (max(0.0, min(x, 1.0)), max(0.0, min(y, 1.0)))
            for x, y in points
            if x <= 1.0 and y <= 1.0
        }
    )
    area = 0.0
    best_y = 1.0
    previous_x = 0.0
    for x, y in bounded:
        area += max(0.0, x - previous_x) * (1.0 - best_y)
        best_y = min(best_y, y)
        previous_x = x
    area += max(0.0, 1.0 - previous_x) * (1.0 - best_y)
    return area
