from dataclasses import dataclass
from math import isfinite

from .Config import Vector, moving_velocity, vector
from .MotionLimits import MotionLimits
from .Task import Task


@dataclass(frozen=True)
class Problem:
    tasks: tuple[Task, ...]
    start: Vector
    end: Vector
    time_budgets: tuple[float, ...]
    limits: tuple[MotionLimits, ...]
    initial_velocities: tuple[Vector, ...]
    name: str = "instance"
    schema_version: int = 1

    def __post_init__(self):
        object.__setattr__(self, "tasks", tuple(self.tasks))
        object.__setattr__(self, "start", vector(self.start))
        object.__setattr__(self, "end", vector(self.end))
        object.__setattr__(
            self, "time_budgets", tuple(float(x) for x in self.time_budgets)
        )
        object.__setattr__(self, "limits", tuple(self.limits))
        object.__setattr__(
            self,
            "initial_velocities",
            tuple(vector(v) for v in self.initial_velocities),
        )
        if self.schema_version != 1:
            raise ValueError("Unsupported instance schema")
        if not self.time_budgets or any(
            not isfinite(b) or b <= 0 for b in self.time_budgets
        ):
            raise ValueError("Flight-time budgets must be positive seconds")
        if (
            len(self.limits) != self.num_agents
            or len(self.initial_velocities) != self.num_agents
        ):
            raise ValueError("Per-agent array counts must match")
        if len({t.id for t in self.tasks}) != len(self.tasks):
            raise ValueError("Duplicate task IDs")
        object.__setattr__(
            self,
            "initial_velocities",
            tuple(
                vel if vel != (0.0, 0.0) else moving_velocity(lim, self.start, self.end)
                for vel, lim in zip(self.initial_velocities, self.limits)
            ),
        )
        for vel, lim in zip(self.initial_velocities, self.limits):
            if any(abs(v) > bound for v, bound in zip(vel, lim.velocity)):
                raise ValueError("Initial velocity exceeds axis limit")

    @property
    def num_agents(self):
        return len(self.time_budgets)

    @property
    def task_map(self):
        return {t.id: t for t in self.tasks}
