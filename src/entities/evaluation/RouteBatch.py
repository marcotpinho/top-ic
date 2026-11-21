from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RouteBatch:
    kind: np.ndarray
    task: np.ndarray
    pos: np.ndarray
    vel: np.ndarray
    nvis: np.ndarray
    task_ids: tuple[str, ...]

    @property
    def size(self) -> int:
        return int(self.kind.shape[0])
