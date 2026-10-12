"""Explicit stage gating and portable full-trajectory output."""

import json
from dataclasses import asdict, replace
from pathlib import Path

from .config import Config, Problem
from .entities.neighborhood import Neighborhood
from .entities.runner import Runner
from .environment import problem_to_dict
from .runner_models import RunResult
from .solution import Solution


def run_optimization(problem: Problem, config: Config | None = None):
    """Run only the team ICC search with a bounded waypoint workspace."""
    config = config or Config(mode="team_kop_icc")
    if config.mode != "team_kop_icc" or config.algorithm != "movns":
        raise ValueError("Only team_kop_icc MOVNS is supported")
    if problem.num_agents < 2:
        raise ValueError("team_kop_icc requires at least two agents")
    if config.waypoint_workspace is None:
        points = [
            problem.start,
            problem.end,
            *[task.position for task in problem.tasks],
        ]
        margin = max(config.comm_range, max(config.waypoint_steps))
        config = replace(
            config,
            waypoint_workspace=(
                min(point[0] for point in points) - margin,
                max(point[0] for point in points) + margin,
                min(point[1] for point in points) - margin,
                max(point[1] for point in points) + margin,
            ),
        )
    unknown = set(config.disabled) - set(Neighborhood.ICC)
    if unknown:
        raise ValueError(f"Unknown disabled neighborhoods: {sorted(unknown)}")
    return Runner(problem, config).run()


def solution_to_dict(s: Solution) -> dict:
    return {
        "objectives": s.objectives,
        "reward": s.evaluation.reward,
        "feasible": s.evaluation.valid,
        "motion_budget_valid": s.evaluation.motion_budget_valid,
        "validation_status": s.evaluation.validation_status,
        "reason": s.evaluation.reason,
        "peak_staleness": s.evaluation.peak_staleness,
        "comm_violation": s.evaluation.comm_violation,
        "completion_times": s.evaluation.completion_times,
        "visit_times": s.evaluation.visit_times,
        "reached_tasks": [sorted(x) for x in s.evaluation.reached_tasks],
        "first_visitors": s.evaluation.first_visitors,
        "routes": [[asdict(v) for v in r] for r in s.routes],
        "meetings": [asdict(p) for p in s.meetings],
        "trajectories": [asdict(t) for t in s.evaluation.trajectories],
        "communication": asdict(s.evaluation.communication)
        if s.evaluation.communication
        else None,
    }


def _tc_slice(front: list[Solution], tc: float) -> dict:
    eligible = [
        index for index, solution in enumerate(front) if solution.objectives[2] == 0
    ]
    selected = []
    for index in eligible:
        candidate = front[index]
        dominated = any(
            other_index != index
            and all(
                front[other_index].objectives[axis] <= candidate.objectives[axis]
                for axis in (0, 1)
            )
            and (
                front[other_index].objectives[:2] != candidate.objectives[:2]
                or other_index < index
            )
            for other_index in eligible
        )
        if not dominated:
            selected.append(index)
    chosen = max(
        (front[index] for index in selected),
        key=lambda solution: (solution.evaluation.reward, -solution.objectives[1]),
        default=None,
    )
    return {
        "tc": tc,
        "front_indices": selected,
        "front_size": len(selected),
        "best_reward": chosen.evaluation.reward if chosen else None,
        "mean_time_at_best_reward": chosen.objectives[1] if chosen else None,
    }


def result_to_dict(result: RunResult) -> dict:
    from .evaluation_core.trajectory import VERSION

    front = list(result.front)
    # Violation is defined for this run's Tc; other Tc values need independent searches.
    slice_at_tc = _tc_slice(front, result.config.recurrence_bound)
    return {
        "schema_version": 4,
        "reward_policy": "explicit_task_visits",
        "objective_policy": "reward_time_violation",
        "model": "box_double_integrator",
        "connector_version": VERSION,
        "problem": problem_to_dict(result.problem),
        "config": asdict(result.config),
        "status": result.status,
        "elapsed_seconds": result.elapsed_seconds,
        "statistics": result.statistics,
        "front": [solution_to_dict(s) for s in front],
        "tc_slices": [slice_at_tc],
        "feasible_front_indices": slice_at_tc["front_indices"],
        "candidate_bank": [solution_to_dict(s) for s in result.candidate_bank],
        "dominated_archive": [solution_to_dict(s) for s in result.dominated_archive],
    }


def save_result(result: RunResult, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result_to_dict(result), indent=2, allow_nan=False) + "\n"
    )
