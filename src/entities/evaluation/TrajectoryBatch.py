from dataclasses import dataclass

import numpy as np

from ..motion.AgentTrajectory import AgentTrajectory


@dataclass(frozen=True)
class TrajectoryBatch:
    dur: np.ndarray
    pc_n: np.ndarray
    p_pos: np.ndarray
    p_vel: np.ndarray
    p_acc: np.ndarray
    p_len: np.ndarray
    p_t0: np.ndarray
    comp: np.ndarray
    trajectories: tuple[tuple[AgentTrajectory, ...], ...]
    visit_times: tuple[tuple[tuple, ...], ...]

    @property
    def size(self) -> int:
        return int(self.comp.shape[0])
