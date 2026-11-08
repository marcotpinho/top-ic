"""Candidate evaluation and epsilon-front/pool updates for the new Runner."""

from collections import Counter
from dataclasses import replace
from math import isfinite
from typing import TYPE_CHECKING

from ..solution import Solution
from ..velocity_initialization import initialize_solution_velocities
from .budget_repair import repair_over_budget
from .profiling import profiling

if TYPE_CHECKING:
    from .runner import Runner


INITIALIZATION_FAMILIES = {
    "initialization",
    "construction",
    "cooperative_seed",
    "partition_seed",
}


def _record_initialization(
    runner: "Runner",
    family: str,
    solution: Solution,
    outcome: str,
) -> None:
    """Record every initialization proposal before search conclusions are drawn."""
    if family not in INITIALIZATION_FAMILIES:
        return
    evaluation = solution.evaluation
    task_ids = {
        visit.task_id
        for route in solution.routes
        for visit in route
        if visit.kind == "TASK"
    }
    declared_reward = sum(
        task.reward for task in runner.problem.tasks if task.id in task_ids
    )
    reward = evaluation.reward if evaluation is not None else None
    cv = evaluation.comm_violation if evaluation is not None else None
    runner.initialization_history.append(
        {
            "sequence": len(runner.initialization_history) + 1,
            "family": family,
            "exact_evaluations": runner.counts["exact_evaluations"],
            "outcome": outcome,
            "valid": evaluation.valid if evaluation is not None else False,
            "declared_reward": declared_reward,
            "evaluated_reward": reward
            if reward is not None and isfinite(reward)
            else None,
            "cv": cv if cv is not None and isfinite(cv) else None,
            "objectives": list(evaluation.objectives)
            if evaluation is not None
            and all(isfinite(value) for value in evaluation.objectives)
            else None,
            "reason": evaluation.reason if evaluation is not None else "",
        }
    )


def _initialize_velocities(runner: "Runner", solution: Solution) -> Solution | None:
    routes = initialize_solution_velocities(
        solution.routes,
        runner.problem.limits,
        runner.config,
        runner.rng,
    )
    if routes is None:
        return None
    return replace(solution, routes=routes, evaluation=None)


def _record_acceptance(runner: "Runner", scored: Solution, row) -> None:
    runner.counts["accepted"] += 1
    row["accepted"] += 1
    row["accepted_front"] += 1
    runner.history.append(
        {
            "evaluations": runner.counts["evaluated"],
            "front": len(runner.archive.front),
            "reward": max(item.evaluation.reward for item in runner.archive.front),
        }
    )


def _prepare_candidate(
    runner: "Runner", solution: Solution, family: str, row: Counter
) -> Solution | None:
    runner.counts["generated"] += 1
    row["generated"] += 1
    if runner.active_base is not None:
        for agent, (candidate_route, base_route) in enumerate(
            zip(solution.routes, runner.active_base.routes)
        ):
            if candidate_route != base_route:
                row[f"agent_{agent}_candidates"] += 1
    candidate = solution
    if family in INITIALIZATION_FAMILIES:
        candidate = _initialize_velocities(runner, solution)
    if candidate is None:
        runner.counts["initial_velocity_sampling_failed"] += 1
        runner.counts["invalid"] += 1
        row["invalid"] += 1
        row["invalid_reason:initial velocity sampling failed"] += 1
        _record_initialization(runner, family, solution, "velocity_sampling_failed")
        return None
    if candidate.key in runner.seen:
        runner.counts["duplicate"] += 1
        runner.counts["cache_hits"] += 1
        row["cache_hits"] += 1
        _record_initialization(runner, family, candidate, "duplicate")
        return None
    runner.seen.add(candidate.key)
    return candidate


def _evaluate(runner: "Runner", candidate: Solution, row: Counter) -> Solution:
    misses_before = runner.evaluator.cache_misses
    hits_before = runner.evaluator.cache_hits
    with profiling(runner.profile, "evaluator_seconds"):
        scored = runner.evaluator.evaluate(candidate)
    runner.counts["evaluated"] += 1
    row["evaluated"] += 1
    exact = runner.evaluator.cache_misses - misses_before
    cache_hits = runner.evaluator.cache_hits - hits_before
    runner.counts["exact_evaluations"] += exact
    runner.counts["cache_hits"] += cache_hits
    row["exact_evaluations"] += exact
    row["cache_hits"] += cache_hits
    return scored


def _repair_candidate(
    runner: "Runner", scored: Solution, family: str, row: Counter
) -> tuple[Solution | None, Counter | None, bool]:
    repair_row = None
    repair_attempted = False
    if (
        not scored.evaluation.valid
        and not scored.evaluation.motion_budget_valid
        and scored.evaluation.completion_times
        and scored.evaluation.trajectories
    ):
        repair_attempted = True
        runner.counts["invalid"] += 1
        row["invalid"] += 1
        reason = scored.evaluation.reason or scored.evaluation.validation_status
        row[f"invalid_reason:{reason}"] += 1
        preview_count = runner.counts["budget_repair_probes"]
        repaired, repair_record = repair_over_budget(runner, scored)
        repair_record["source_family"] = family
        runner.budget_repairs.append(repair_record)
        repair_row = runner.by_family.setdefault("budget_repair_drop", Counter())
        repair_row["generated"] += runner.counts["budget_repair_probes"] - preview_count
        repair_row["dropped_tasks"] += len(repair_record["tasks_dropped"])
        if repaired is not None and not runner.exhausted():
            if repaired.key in runner.seen:
                runner.counts["duplicate"] += 1
                runner.counts["cache_hits"] += 1
                repair_row["cache_hits"] += 1
                _record_initialization(
                    runner, family, repaired, "duplicate_after_repair"
                )
                return None, repair_row, repair_attempted
            runner.seen.add(repaired.key)
            scored = _evaluate(runner, repaired, repair_row)
            if scored.evaluation.valid:
                repair_row["valid"] += 1
            else:
                runner.counts["invalid"] += 1
                repair_row["invalid"] += 1
                reason = scored.evaluation.reason or scored.evaluation.validation_status
                repair_row[f"invalid_reason:{reason}"] += 1
    return scored, repair_row, repair_attempted


def _update_archives(
    runner: "Runner",
    scored: Solution,
    family: str,
    row: Counter,
    repair_row: Counter | None,
) -> Solution:
    runner.counts["valid"] += 1
    acceptance_row = repair_row or row
    if repair_row is None:
        row["valid"] += 1
    was_pool_base = runner.active_base_source == "pool"
    if runner.archive.add(scored):
        _record_acceptance(runner, scored, acceptance_row)
        _record_initialization(runner, family, scored, "front")
        if was_pool_base:
            runner.counts["pool_to_front"] += 1
            if family == "communication_repair":
                runner.counts["pool_to_front_from_repair"] += 1
    elif runner.archive.last_addition["pool"]:
        runner.counts["accepted_pool"] += 1
        acceptance_row["accepted_pool"] += 1
        _record_initialization(runner, family, scored, "pool")
    else:
        _record_initialization(runner, family, scored, "discarded")
    return scored


def evaluate_candidate(
    runner: "Runner", solution: Solution, family: str
) -> Solution | None:
    """Score one complete solution and update front/pool (eqs. 1–16)."""
    if runner.exhausted():
        return None
    row = runner.by_family.setdefault(family, Counter())

    # Prepare velocities and reject duplicate candidates.
    candidate = _prepare_candidate(runner, solution, family, row)
    if candidate is None:
        return None

    # Evaluate the candidate and record time and cache usage.
    scored = _evaluate(runner, candidate, row)

    # Repair budget violations and evaluate the repaired candidate.
    scored, repair_row, repair_attempted = _repair_candidate(
        runner, scored, family, row
    )
    if scored is None:
        return None

    # Discard invalid candidates without counting a repair twice.
    if not scored.evaluation.valid:
        if not repair_attempted:
            runner.counts["invalid"] += 1
            reason = scored.evaluation.reason or scored.evaluation.validation_status
            row[f"invalid_reason:{reason}"] += 1
        _record_initialization(runner, family, scored, "invalid")
        return None

    # Update F and P and record the candidate's acceptance.
    return _update_archives(runner, scored, family, row, repair_row)
