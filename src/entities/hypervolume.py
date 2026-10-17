"""Exact three-objective hypervolume for normalized minimization points."""

from bisect import bisect_left
from collections.abc import Iterable
from itertools import pairwise

Point3D = tuple[float, float, float]


def hypervolume_3d(points: Iterable[Point3D]) -> float:
    """Measure minimization hypervolume against normalized reference (1, 1, 1)."""
    reference = (1.0, 1.0, 1.0)
    bounded = [
        (
            max(0.0, min(point[0], reference[0])),
            max(0.0, min(point[1], reference[1])),
            max(0.0, min(point[2], reference[2])),
        )
        for point in points
        if all(value <= 1.0 for value in point)
    ]
    if not bounded:
        return 0.0
    x_values = sorted({point[0] for point in bounded} | {reference[0]})
    y_values = sorted({point[1] for point in bounded} | {reference[1]})
    y_widths = [right - left for left, right in pairwise(y_values)]
    lowest_z = [reference[2]] * len(y_widths)
    points_by_x: dict[float, list[Point3D]] = {}
    for point in bounded:
        points_by_x.setdefault(point[0], []).append(point)
    volume = 0.0
    for x_left, x_right in pairwise(x_values):
        for point in points_by_x.get(x_left, []):
            y_index = bisect_left(y_values, point[1])
            for segment in range(y_index, len(y_widths)):
                lowest_z[segment] = min(lowest_z[segment], point[2])
        area = sum(
            width * (reference[2] - z_minimum)
            for width, z_minimum in zip(y_widths, lowest_z)
        )
        volume += (x_right - x_left) * area
    return volume
