"""Validated, explicit physical inputs and search settings."""
from dataclasses import dataclass
from math import isfinite, cos, sin, pi

Vector = tuple[float, float]


def vector(value) -> Vector:
    if len(value) != 2 or not all(isfinite(float(x)) for x in value):
        raise ValueError("Expected a finite 2D vector")
    return tuple(float(x) for x in value)


@dataclass(frozen=True)
class MotionLimits:
    velocity: Vector = (3.0, 3.0)
    acceleration: Vector = (1.5, 1.5)

    def __post_init__(self):
        object.__setattr__(self, "velocity", vector(self.velocity))
        object.__setattr__(self, "acceleration", vector(self.acceleration))
        if min(*self.velocity, *self.acceleration) <= 0:
            raise ValueError("Axis limits must be positive")


@dataclass(frozen=True)
class Task:
    id: str
    position: Vector
    reward: float

    def __post_init__(self):
        object.__setattr__(self, "position", vector(self.position))
        if not self.id or not isfinite(self.reward) or self.reward < 0:
            raise ValueError("Tasks need a stable ID and finite nonnegative reward")


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
        object.__setattr__(self, "time_budgets", tuple(float(x) for x in self.time_budgets))
        object.__setattr__(self, "limits", tuple(self.limits))
        object.__setattr__(self, "initial_velocities", tuple(vector(v) for v in self.initial_velocities))
        if self.schema_version != 1:
            raise ValueError("Unsupported instance schema")
        if not self.time_budgets or any(not isfinite(b) or b <= 0 for b in self.time_budgets):
            raise ValueError("Flight-time budgets must be positive seconds")
        if len(self.limits) != self.num_agents or len(self.initial_velocities) != self.num_agents:
            raise ValueError("Per-agent array counts must match")
        if len({t.id for t in self.tasks}) != len(self.tasks):
            raise ValueError("Duplicate task IDs")
        for vel, lim in zip(self.initial_velocities, self.limits):
            if any(abs(v) > bound for v, bound in zip(vel, lim.velocity)):
                raise ValueError("Initial velocity exceeds axis limit")

    @property
    def num_agents(self):
        return len(self.time_budgets)

    @property
    def task_map(self):
        return {t.id: t for t in self.tasks}


@dataclass(frozen=True)
class Config:
    mode: str = "single_kop"
    seed: int = 42
    max_seconds: float = 30.0
    max_evaluations: int = 2000
    max_iterations: int = 100
    archive_size: int = 40
    headings: int = 4
    eps_reward: float = 1.0
    eps_time: float = 0.1
    speed_fractions: tuple[float, ...] = (0.0, 0.5, 1.0)
    disabled: tuple[str, ...] = ()
    algorithm: str = "movns"

    def __post_init__(self):
        if self.mode not in ("single_kop", "team_kop", "team_kop_icc"):
            raise ValueError("Unknown problem mode")
        if self.algorithm not in ("movns", "lns"):
            raise ValueError("Unknown search algorithm")
        if not isfinite(self.max_seconds) or not 0 < self.max_seconds <= 600:
            raise ValueError("Runtime limit must be in (0,600] seconds")
        if min(self.max_evaluations, self.max_iterations, self.archive_size, self.headings) <= 0:
            raise ValueError("Search counts must be positive")
        if not all(isfinite(e) and e>0 for e in (self.eps_reward,self.eps_time)):
            raise ValueError("Epsilon widths must be positive and finite")
        if not self.speed_fractions or any(not isfinite(f) or not 0 <= f <= 1 for f in self.speed_fractions):
            raise ValueError("Speed fractions must be in [0,1]")


def velocity_menu(limits: MotionLimits, config: Config):
    states = {(0.0, 0.0)}
    for h in range(config.headings):
        direction = (cos(2*pi*h/config.headings), sin(2*pi*h/config.headings))
        maximum = min(limits.velocity[d]/abs(direction[d]) for d in range(2) if abs(direction[d]) > 1e-12)
        for fraction in config.speed_fractions:
            states.add(tuple(0.0 if abs(x) < 1e-12 else round(x, 12) for x in (fraction*maximum*direction[0], fraction*maximum*direction[1])))
    return tuple(sorted(states))
