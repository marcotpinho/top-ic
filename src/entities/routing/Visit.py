from dataclasses import dataclass

from ..problem.Config import Vector, vector


@dataclass(frozen=True)
class Visit:
    id: str
    kind: str
    position: Vector
    velocity: Vector
    task_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "position", vector(self.position))
        object.__setattr__(self, "velocity", vector(self.velocity))
        if self.kind not in ("START", "TASK", "FREE", "END"):
            raise ValueError("Invalid visit kind")
        if self.velocity == (0.0, 0.0):
            raise ValueError("Visit velocity must be nonzero")
        if not self.id:
            raise ValueError("Visit needs a stable ID")
        if self.kind == "TASK" and not self.task_id:
            raise ValueError("Task visit needs a task ID")
