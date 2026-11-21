"""Bounded communication repair driven by the current ordered-pair bottleneck."""

from math import atan2, cos, hypot, sin
from itertools import islice
from typing import TYPE_CHECKING

from ..solution import Solution, Visit
from .neighborhoods.common import fresh_id, in_workspace

if TYPE_CHECKING:
    from .search.Runner import Runner


def _bottleneck_agents(solution: Solution) -> tuple[int, int]:
    bottleneck = solution.evaluation.communication.bottleneck
    return (bottleneck[0], bottleneck[1]) if bottleneck else (0, 1)


def _ranked_visit_pairs(solution: Solution, limit: int = 8):
    source, receiver = _bottleneck_agents(solution)
    source_times = solution.evaluation.visit_times[source]
    receiver_times = solution.evaluation.visit_times[receiver]
    pairs = []
    for source_index, source_visit in enumerate(solution.routes[source][:-1]):
        for receiver_index, receiver_visit in enumerate(solution.routes[receiver][:-1]):
            time_gap = abs(
                source_times[source_index][0] - receiver_times[receiver_index][0]
            )
            distance = hypot(
                source_visit.position[0] - receiver_visit.position[0],
                source_visit.position[1] - receiver_visit.position[1],
            )
            pairs.append(
                (time_gap, distance, source, source_index, receiver, receiver_index)
            )
    return sorted(pairs)[:limit]


def _invitation_candidates(runner: "Runner", solution: Solution):
    radius = 0.9 * runner.config.comm_range
    offsets = (-0.25, 0.0, 0.25)
    for _, _, host, host_index, guest, guest_index in _ranked_visit_pairs(solution):
        host_visit = solution.routes[host][host_index]
        guest_visit = solution.routes[guest][guest_index]
        angle = atan2(
            guest_visit.position[1] - host_visit.position[1],
            guest_visit.position[0] - host_visit.position[0],
        )
        for angle_offset in offsets:
            point = (
                host_visit.position[0] + radius * cos(angle + angle_offset),
                host_visit.position[1] + radius * sin(angle + angle_offset),
            )
            if not in_workspace(point, runner.config.waypoint_workspace):
                continue
            guest_route = list(solution.routes[guest])
            guest_route.insert(
                max(1, guest_index),
                Visit(
                    fresh_id(solution, "invite"),
                    "FREE",
                    point,
                    guest_route[max(1, guest_index) - 1].velocity,
                ),
            )
            routes = list(solution.routes)
            routes[guest] = tuple(guest_route)
            yield Solution(tuple(routes))


def _invitation_set(runner: "Runner", solution: Solution) -> list[Solution]:
    candidates = {}
    if runner.config.batch_eval:
        from ..batch.repair import invitation_candidates

        generated = invitation_candidates(
            solution,
            _ranked_visit_pairs(solution),
            runner.problem,
            runner.config,
        )
    else:
        generated = _invitation_candidates(runner, solution)
    for candidate in generated:
        candidates.setdefault(candidate.key, candidate)
    values = list(candidates.values())
    runner.rng.shuffle(values)
    return values[: runner.config.neighborhood_candidates]


def _repair_candidates(
    runner: "Runner", solution: Solution, family: str
) -> list[Solution]:
    if family == "free_invitation":
        return _invitation_set(runner, solution)
    if family not in runner.neighborhood.names:
        return []
    limit = max(1, runner.config.neighborhood_candidates // 4)
    return list(
        islice(
            runner.neighborhood.generate(
                family,
                solution,
                phase="communication_repair",
            ),
            limit,
        )
    )


def _score_family(
    runner: "Runner", current: Solution, family: str
) -> list[Solution]:
    candidates = _repair_candidates(runner, current, family)
    label = (
        "communication_repair"
        if family == "free_invitation"
        else f"communication_repair_{family}"
    )
    if runner.config.batch_eval:
        return [
            evaluated
            for evaluated in runner.evaluate_batch(candidates, label, current)
            if evaluated is not None
        ]
    scored = []
    for candidate in candidates:
        if runner.exhausted():
            break
        evaluated = runner.evaluate(candidate, label, current)
        if evaluated is not None:
            scored.append(evaluated)
    return scored


def repair_communication(runner: "Runner", solution: Solution) -> Solution:
    """Run at most three exact best-improvement CV repair rounds."""
    if solution.evaluation.comm_violation <= runner.config.numerical_tolerance:
        return solution
    runner.counts["communication_repair_calls"] += 1
    initial_cv = solution.evaluation.comm_violation
    current = solution
    reduced = False
    for round_index in range(runner.config.communication_repair_rounds):
        best = None
        selected_family = None
        for family in ("assignment", "two_opt", "velocity_change", "free_invitation"):
            scored = _score_family(runner, current, family)
            if not scored:
                continue
            candidate = min(
                scored,
                key=lambda item: (
                    item.evaluation.comm_violation,
                    -item.evaluation.reward,
                    item.objectives[1],
                    repr(item.key),
                ),
            )
            if candidate.evaluation.comm_violation < current.evaluation.comm_violation:
                best = candidate
                selected_family = family
                break
        if best is None:
            break
        reduced = True
        current = best
        runner.repair_history.append(
            {
                "round": round_index + 1,
                "before_cv": initial_cv if round_index == 0 else None,
                "after_cv": current.evaluation.comm_violation,
                "family": selected_family,
            }
        )
        if current.evaluation.comm_violation <= runner.config.numerical_tolerance:
            runner.counts["communication_repair_zeroed"] += 1
            break
    if reduced:
        runner.counts["communication_repair_reduced"] += 1
    return current
