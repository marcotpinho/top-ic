"""Candidate evaluation and epsilon-front/pool updates for the new Runner."""

from collections import Counter
from dataclasses import replace
from typing import TYPE_CHECKING

from ..solution import Solution
from ..velocity_dp import refine_route_velocities

if TYPE_CHECKING:
    from .runner import Runner


def _refine(runner: "Runner", solution: Solution) -> Solution | None:
    forced = {
        identity
        for meeting in solution.meetings
        for identity in (meeting.left, meeting.right)
    }
    routes = []
    for agent, route in enumerate(solution.routes):
        refined = refine_route_velocities(
            route, runner.problem.limits[agent], runner.config, forced
        )
        if refined is None:
            return None
        routes.append(refined)
    return replace(solution, routes=tuple(routes), evaluation=None)


def _record_acceptance(runner: "Runner", scored: Solution, row) -> None:
    runner.counts["accepted"] += 1
    row["accepted"] += 1
    runner.history.append(
        {
            "evaluations": runner.counts["evaluated"],
            "front": len(runner.archive.front),
            "reward": max(item.evaluation.reward for item in runner.archive.front),
        }
    )


def evaluate_candidate(
    runner: "Runner", solution: Solution, family: str
) -> Solution | None:
    """Score one complete solution and update front/pool (eqs. 1–16)."""
    if runner.exhausted():
        return None
    row = runner.by_family.setdefault(family, Counter())
    runner.counts["generated"] += 1
    row["generated"] += 1
    candidate = _refine(runner, solution)
    if candidate is None:
        runner.counts["refinement_failed"] += 1
        return None
    if candidate.key in runner.seen:
        runner.counts["duplicate"] += 1
        return None
    runner.seen.add(candidate.key)
    scored = runner.evaluator.evaluate(candidate)
    runner.counts["evaluated"] += 1
    row["evaluated"] += 1
    if not scored.evaluation.valid:
        runner.counts["invalid"] += 1
        return None
    runner.counts["valid"] += 1
    row["valid"] += 1
    if runner.archive.add(scored):
        _record_acceptance(runner, scored, row)
    return scored
