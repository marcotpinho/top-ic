"""Immutable occurrence-level decisions; caches do not define identity."""
from dataclasses import dataclass, field
from .config import Vector, vector


@dataclass(frozen=True)
class Visit:
    id: str
    kind: str
    position: Vector
    velocity: Vector = (0.,0.)
    task_id: str | None = None
    wait: float = 0.

    def __post_init__(self):
        object.__setattr__(self,"position",vector(self.position))
        object.__setattr__(self,"velocity",vector(self.velocity))
        if self.kind not in ("START","TASK","FREE","END"):
            raise ValueError("Invalid visit kind")
        from math import isfinite
        if not self.id or not isfinite(self.wait) or self.wait<0 or (self.wait>0 and self.velocity!=(0.,0.)):
            raise ValueError("Waiting requires a stopped valid visit")
        if self.kind=="TASK" and not self.task_id:
            raise ValueError("Task visit needs a task ID")


@dataclass(frozen=True)
class Solution:
    routes: tuple[tuple[Visit,...],...]
    evaluation: object = field(default=None,compare=False,repr=False)

    def __post_init__(self):
        object.__setattr__(self,"routes",tuple(tuple(r) for r in self.routes))

    @property
    def key(self):
        return self.routes

    @property
    def objectives(self):
        return self.evaluation.objectives if self.evaluation else None

    def dominates(self,other):
        if self.objectives is None or other.objectives is None:
            return False
        return all(a<=b for a,b in zip(self.objectives,other.objectives)) and any(a<b for a,b in zip(self.objectives,other.objectives))


def direct_solution(problem):
    return Solution(tuple((Visit(f"{m}:start","START",problem.start,problem.initial_velocities[m]),
                           Visit(f"{m}:end","END",problem.end)) for m in range(problem.num_agents)))
