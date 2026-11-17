"""Log-distance RSSI model shared with TOP-CC."""

from math import isfinite, log10

TX_POWER = -30.0
PATH_LOSS_EXPONENT = 2.0
MIN_DISTANCE = 0.1


def rssi(distance: float) -> float:
    if not isfinite(distance) or distance < 0:
        raise ValueError("RSSI distance must be finite and nonnegative")
    return TX_POWER - 10 * PATH_LOSS_EXPONENT * log10(max(distance, MIN_DISTANCE))


def distance_at_rssi(threshold: float) -> float:
    if not isfinite(threshold):
        raise ValueError("RSSI threshold must be finite")
    distance = 10 ** ((TX_POWER - threshold) / (10 * PATH_LOSS_EXPONENT))
    return max(MIN_DISTANCE, distance)


def meets_threshold(distance: float, threshold: float) -> bool:
    return rssi(distance) >= threshold
