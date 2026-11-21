from dataclasses import dataclass

import numpy as np

from .ContactRecord import ContactRecord


@dataclass(frozen=True)
class ContactBatch:
    intervals: np.ndarray
    counts: np.ndarray
    status: np.ndarray
    pair_agents: tuple[tuple[int, int], ...]
    records: tuple[tuple[ContactRecord, ...], ...]
