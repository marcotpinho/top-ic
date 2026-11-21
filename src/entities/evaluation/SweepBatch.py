from dataclasses import dataclass

import numpy as np

from .CommunicationResult import CommunicationResult


@dataclass(frozen=True)
class SweepBatch:
    results: tuple[CommunicationResult | None, ...]
    peaks: np.ndarray
    violation: np.ndarray
    delta: np.ndarray
    integrated_excess: np.ndarray
    status: np.ndarray
