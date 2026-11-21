"""Validated, explicit physical inputs and search settings."""

from dataclasses import dataclass
from math import atan2, cos, isfinite, pi, sin

Vector = tuple[float, float]


def vector(value) -> Vector:
    if len(value) != 2 or not all(isfinite(float(x)) for x in value):
        raise ValueError("Expected a finite 2D vector")
    return tuple(float(x) for x in value)


def moving_velocity(limits, start: Vector, end: Vector) -> Vector:
    """Use the nearest 45-degree heading at 10% of its axis-limited speed."""
    angle = round(atan2(end[1] - start[1], end[0] - start[0]) / (pi / 4)) * (pi / 4)
    direction = (cos(angle), sin(angle))
    maximum = min(
        limits.velocity[d] / abs(direction[d])
        for d in range(2)
        if abs(direction[d]) > 1e-12
    )
    return tuple(0.0 if abs(v) < 1e-12 else 0.1 * maximum * v for v in direction)


@dataclass(frozen=True)
class Config:
    seed: int = 42
    evaluation_workers: int = 1
    evaluation_batch_size: int = 8
    evaluation_cache_size: int = 4096
    route_cache_size: int = 4096
    incremental_evaluation: bool = True
    verify_incremental: bool = False
    max_seconds: float = 30.0
    max_evaluations: int = 2000
    max_iterations: int = 100
    initialization_budget_fraction: float = 0.2
    neighborhood_hv_tau: float = 0.0
    neighborhood_max_passes: int = 3
    kinematic_refinement_interval: int = 3
    archive_size: int = 100
    headings: int = 8
    eps_reward: float = 1.0
    eps_time: float = 0.1
    speed_fractions: tuple[float, ...] = (0.1, 0.25, 0.5, 0.75, 1.0)
    velocity_segment_lengths: tuple[int, ...] = (2, 3)
    disabled: tuple[str, ...] = ()
    comm_range: float = 2.0
    recurrence_bound: float = 5.0
    dominated_archive_size: int = 100
    pool_max_age: int = 5
    communication_repair_rounds: int = 3
    pool_selection_enabled: bool = True
    selection_policy: str = "elite_mixture"
    elite_selection_probability: float = 0.3
    pool_selection_probability: float = 0.3
    elite_cooldown_after: int = 3
    elite_cooldown_iterations: int = 3
    waypoint_workspace: tuple[float, float, float, float] | None = None
    waypoint_steps: tuple[float, ...] = (1.0, 0.25)
    neighborhood_candidates: int = 120
    free_segment_radius: float | None = None  # Lateral offset bound; None uses R.
    recreate_sample_slots: int = 8
    recreate_noise_scale: float = 1.0
    shake_candidate_prefix: int = 200  # Maximum candidates inspected in a shake.
    relay_radius_fractions: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0)  # Of R.
    geometry_tolerance: float = 1e-9
    contact_tolerance: float = 2e-7
    numerical_tolerance: float = 1e-13
    budget_tolerance: float = 1e-7
    batch_eval: bool = False
    batch_neighborhoods: bool = False
    verify_batch_eval: bool = False
    batch_verify_fraction: float = 0.0
    ruin_recreate_enabled: bool = True

    @property
    def communication_rssi_threshold(self) -> float:
        from ...evaluation_core.rssi import rssi

        return rssi(self.comm_range)

    def __post_init__(self):
        # JSON arrays must not leave mutable containers inside a frozen config.
        for name in (
            "speed_fractions",
            "velocity_segment_lengths",
            "disabled",
            "waypoint_steps",
            "relay_radius_fractions",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if self.waypoint_workspace is not None:
            object.__setattr__(
                self, "waypoint_workspace", tuple(self.waypoint_workspace)
            )
        if not isfinite(self.max_seconds) or not 0 < self.max_seconds <= 3600:
            raise ValueError("Runtime limit must be in (0,3600] seconds")
        if (
            min(
                self.max_evaluations,
                self.evaluation_workers,
                self.evaluation_batch_size,
                self.evaluation_cache_size,
                self.route_cache_size,
                self.max_iterations,
                self.neighborhood_max_passes,
                self.kinematic_refinement_interval,
                self.archive_size,
                self.dominated_archive_size,
                self.headings,
                self.neighborhood_candidates,
                self.recreate_sample_slots,
            )
            <= 0
        ):
            raise ValueError("Search counts must be positive")
        if self.pool_max_age < 0 or self.communication_repair_rounds < 0:
            raise ValueError("Pool age and repair rounds must be nonnegative")
        if self.selection_policy not in (
            "elite_mixture",
            "nd_count",
            "legacy_fraction",
        ):
            raise ValueError("Unknown archive selection policy")
        if (
            not isfinite(self.elite_selection_probability)
            or not isfinite(self.pool_selection_probability)
            or self.elite_selection_probability < 0
            or self.pool_selection_probability < 0
            or self.elite_selection_probability + self.pool_selection_probability > 1
        ):
            raise ValueError(
                "Elite and pool probabilities must be nonnegative and sum to at most 1"
            )
        if self.elite_cooldown_after < 1 or self.elite_cooldown_iterations < 0:
            raise ValueError("Elite cooldown parameters must be nonnegative")
        if not isfinite(self.neighborhood_hv_tau) or self.neighborhood_hv_tau < 0:
            raise ValueError("Neighborhood hypervolume threshold must be nonnegative")
        if (
            not isfinite(self.batch_verify_fraction)
            or not 0 <= self.batch_verify_fraction <= 1
        ):
            raise ValueError("Batch verification fraction must be in [0,1]")
        if (
            not isfinite(self.initialization_budget_fraction)
            or not 0 < self.initialization_budget_fraction < 1
        ):
            raise ValueError("Initialization budget fraction must be in (0,1)")
        if not isfinite(self.recreate_noise_scale) or self.recreate_noise_scale < 0:
            raise ValueError("Recreate noise scale must be finite and nonnegative")
        if self.free_segment_radius is not None and (
            not isfinite(self.free_segment_radius) or self.free_segment_radius <= 0
        ):
            raise ValueError("Free segment radius must be positive and finite")
        if self.shake_candidate_prefix <= 0:
            raise ValueError("Neighborhood limits must be positive")
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
            )
        ):
            raise ValueError("Tolerances must be positive and finite")
        if not all(isfinite(e) and e > 0 for e in (self.eps_reward, self.eps_time)):
            raise ValueError("Epsilon widths must be positive and finite")
        if (
            not isfinite(self.comm_range)
            or self.comm_range <= 0
            or not isfinite(self.recurrence_bound)
            or self.recurrence_bound < 0
        ):
            raise ValueError("Communication range must be positive and window nonnegative")
        if not all(isfinite(s) and s > 0 for s in self.waypoint_steps):
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
            not isfinite(f) or not 0.1 <= f <= 1 for f in self.speed_fractions
        ):
            raise ValueError("Speed fractions must be in [0.1,1]")
        if (
            not self.velocity_segment_lengths
            or any(
                not isinstance(length, int) or length < 2
                for length in self.velocity_segment_lengths
            )
            or len(set(self.velocity_segment_lengths))
            != len(self.velocity_segment_lengths)
        ):
            raise ValueError("Velocity segment lengths must be distinct integers >= 2")


def velocity_menu(limits, config: Config):
    states = set()
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
