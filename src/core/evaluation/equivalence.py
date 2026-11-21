from dataclasses import fields, is_dataclass

import numpy as np


def equivalent(first, second, tolerance=1e-9):
    if type(first) is not type(second):
        return False
    if is_dataclass(first):
        return all(
            equivalent(getattr(first, item.name), getattr(second, item.name), tolerance)
            for item in fields(first)
        )
    if isinstance(first, (tuple, list)):
        return len(first) == len(second) and all(
            equivalent(a, b, tolerance) for a, b in zip(first, second)
        )
    if isinstance(first, (float, np.floating)):
        return bool(np.isclose(first, second, rtol=0.0, atol=tolerance, equal_nan=True))
    return first == second
