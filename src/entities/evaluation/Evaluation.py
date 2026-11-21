from dataclasses import dataclass

from ..motion.AgentTrajectory import AgentTrajectory


@dataclass(frozen=True)
class Evaluation:
    valid: bool
    objectives: tuple[float, ...]
    completion_times: tuple[float, ...]
    reached_tasks: tuple[frozenset[str], ...]
    trajectories: tuple[AgentTrajectory, ...]
    reason: str = ""
    peak_staleness: float | None = None
    first_visitors: tuple[tuple[str, int, float], ...] = ()
    motion_budget_valid: bool = False
    comm_violation: float = 0.0
    communication: object = None
    visit_times: tuple = ()
    validation_status: str = "valid"
    evaluation_context: tuple = ()

    @property
    def reward(self) -> float:
        return -self.objectives[0]
