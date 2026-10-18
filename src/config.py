"""Validated, explicit physical inputs and search settings."""

from dataclasses import dataclass
from itertools import pairwise
from math import cos, isfinite, pi, sin

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
    mode: str = "team_kop_icc"
    seed: int = 42
    max_seconds: float = 30.0
    max_evaluations: int = 2000
    max_iterations: int = 100
    neighborhood_hv_tau: float = 0.0
    neighborhood_max_passes: int = 3
    archive_size: int = 200
    front_selection_prob: float = 0.9
    headings: int = 4
    eps_reward: float = 1.0
    eps_time: float = 0.1
    eps_delta: float | None = None
    eps_violation: float | None = None
    tc_sweep: tuple[float, ...] = ()
    speed_fractions: tuple[float, ...] = (0.0, 0.5, 1.0)
    disabled: tuple[str, ...] = ()
    algorithm: str = "movns"
    comm_range: float = 2.0
    handshake_time: float = 0.5
    recurrence_bound: float = 5.0
    dominated_archive_size: int = 40
    working_pool_size: int | None = None  # legacy schema-2 input alias
    max_free_waypoints: int = 3
    waypoint_workspace: tuple[float, float, float, float] | None = None
    waypoint_steps: tuple[float, ...] = (1.0, 0.25)
    wait_steps: tuple[float, ...] = (0.25, 1.0)
    candidate_bank_size: int = 80
    neighborhood_candidates: int = 120
    recreate_sample_slots: int = 8
    recreate_noise_scale: float = 1.0
    shake_candidate_prefix: int = 200  # Maximum candidates inspected in a shake.
    meeting_link_limit: int = 8  # Existing visit pairs retained per agent pair.
    meeting_slot_limit: int = 3  # Candidate slots on each meeting route.
    invite_radius_fraction: float = 0.9  # Place invitations within 90% of R.
    rendezvous_radius_fractions: tuple[float, ...] = (0.5, 0.9, 1.0)
    relay_radius_fractions: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0)  # Of R.
    geometry_tolerance: float = 1e-9
    contact_tolerance: float = 2e-7
    numerical_tolerance: float = 1e-13
    budget_tolerance: float = 1e-7
    schedule_tolerance: float = 1e-8

    def __post_init__(self):
        # JSON arrays must not leave mutable containers inside a frozen config.
        for name in (
            "speed_fractions",
            "disabled",
            "waypoint_steps",
            "wait_steps",
            "rendezvous_radius_fractions",
            "relay_radius_fractions",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if self.working_pool_size is not None:
            object.__setattr__(self, "dominated_archive_size", self.working_pool_size)
        object.__setattr__(self, "tc_sweep", tuple(float(x) for x in self.tc_sweep))
        if self.waypoint_workspace is not None:
            object.__setattr__(
                self, "waypoint_workspace", tuple(self.waypoint_workspace)
            )
        if self.mode != "team_kop_icc":
            raise ValueError("Only team_kop_icc is supported")
        if self.algorithm != "movns":
            raise ValueError("Only MOVNS is supported")
        if not isfinite(self.max_seconds) or not 0 < self.max_seconds <= 3600:
            raise ValueError("Runtime limit must be in (0,3600] seconds")
        if (
            min(
                self.max_evaluations,
                self.max_iterations,
                self.neighborhood_max_passes,
                self.archive_size,
                self.headings,
                self.neighborhood_candidates,
                self.recreate_sample_slots,
            )
            <= 0
        ):
            raise ValueError("Search counts must be positive")
        if not isfinite(self.neighborhood_hv_tau) or self.neighborhood_hv_tau < 0:
            raise ValueError("Neighborhood hypervolume threshold must be nonnegative")
        if not isfinite(self.recreate_noise_scale) or self.recreate_noise_scale < 0:
            raise ValueError("Recreate noise scale must be finite and nonnegative")
        if (
            min(
                self.shake_candidate_prefix,
                self.meeting_link_limit,
                self.meeting_slot_limit,
            )
            <= 0
        ):
            raise ValueError("Neighborhood limits must be positive")
        if not 0 < self.invite_radius_fraction <= 1 or any(
            not 0 < fraction <= 1 for fraction in self.rendezvous_radius_fractions
        ):
            raise ValueError("Communication radius fractions must be in (0, 1]")
        if any(
            not isfinite(fraction) or fraction <= 0
            for fraction in self.relay_radius_fractions
        ):
            raise ValueError("Relay radius fractions must be positive and finite")
        if any(
            value <= 0 or not isfinite(value)
            for value in (
                self.geometry_tolerance,
                self.contact_tolerance,
                self.numerical_tolerance,
                self.budget_tolerance,
                self.schedule_tolerance,
            )
        ):
            raise ValueError("Tolerances must be positive and finite")
        if (
            not isfinite(self.front_selection_prob)
            or not 0 <= self.front_selection_prob <= 1
        ):
            raise ValueError("Front-selection probability must be in [0,1]")
        if not all(isfinite(e) and e > 0 for e in (self.eps_reward, self.eps_time)):
            raise ValueError("Epsilon widths must be positive and finite")
        if self.eps_delta is not None and (
            not isfinite(self.eps_delta) or self.eps_delta <= 0
        ):
            raise ValueError("Delta epsilon must be positive and finite")
        if self.eps_violation is not None and (
            not isfinite(self.eps_violation) or self.eps_violation <= 0
        ):
            raise ValueError("Violation epsilon must be positive and finite")
        if any(not isfinite(t) or t < 0 for t in self.tc_sweep) or len(
            set(self.tc_sweep)
        ) != len(self.tc_sweep):
            raise ValueError(
                "Tc sweep values must be distinct nonnegative finite seconds"
            )
        if (
            not isfinite(self.comm_range)
            or self.comm_range <= 0
            or not isfinite(self.handshake_time)
            or self.handshake_time < 0
            or not isfinite(self.recurrence_bound)
            or self.recurrence_bound <= 0
        ):
            raise ValueError(
                "Communication range/window must be positive, handshake nonnegative"
            )
        if (
            min(
                self.dominated_archive_size,
                self.max_free_waypoints,
                self.candidate_bank_size,
            )
            < 0
        ):
            raise ValueError("Pool and waypoint limits must be nonnegative")
        if not all(
            isfinite(s) and s > 0 for s in self.waypoint_steps + self.wait_steps
        ):
            raise ValueError("Neighborhood step sizes must be positive")
        if self.waypoint_workspace is not None and (
            len(self.waypoint_workspace) != 4
            or not all(isfinite(x) for x in self.waypoint_workspace)
            or not (
                self.waypoint_workspace[0] < self.waypoint_workspace[1]
                and self.waypoint_workspace[2] < self.waypoint_workspace[3]
            )
        ):
            raise ValueError("Workspace must be xmin,xmax,ymin,ymax")
        if not self.speed_fractions or any(
            not isfinite(f) or not 0 <= f <= 1 for f in self.speed_fractions
        ):
            raise ValueError("Speed fractions must be in [0,1]")

    @property
    def delta_resolution(self):
        if self.eps_delta is not None:
            return self.eps_delta
        values = sorted(self.tc_sweep)
        return min((right - left for left, right in pairwise(values)), default=1.0)

    @property
    def violation_resolution(self):
        return (
            self.eps_violation
            if self.eps_violation is not None
            else (self.eps_delta if self.eps_delta is not None else 1.0)
        )


def velocity_menu(limits: MotionLimits, config: Config):
    states = {(0.0, 0.0)}
    for h in range(config.headings):
        direction = (
            cos(2 * pi * h / config.headings),
            sin(2 * pi * h / config.headings),
        )
        maximum = min(
            limits.velocity[d] / abs(direction[d])
            for d in range(2)
            if abs(direction[d]) > 1e-12
        )
        for fraction in config.speed_fractions:
            states.add(
                tuple(
                    0.0 if abs(x) < 1e-12 else round(x, 12)
                    for x in (
                        fraction * maximum * direction[0],
                        fraction * maximum * direction[1],
                    )
                )
            )
    return tuple(sorted(states))
