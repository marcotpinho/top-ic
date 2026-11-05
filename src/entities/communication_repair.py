"""Bounded communication repair driven by the current ordered-pair bottleneck."""

from dataclasses import replace
from math import atan2, cos, hypot, sin
from typing import TYPE_CHECKING

from ..solution import Solution, Visit
from .neighborhoods.common import edited, fresh_id, in_workspace

if TYPE_CHECKING:
    from .runner import Runner


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


def _link_candidates(runner: "Runner", solution: Solution):
    wait = runner.config.handshake_time
    for _, distance, host, host_index, guest, guest_index in _ranked_visit_pairs(
        solution
    ):
        host_route = list(solution.routes[host])
        guest_route = list(solution.routes[guest])
        if distance <= runner.config.comm_range:
            host_route[host_index] = replace(
                host_route[host_index], velocity=(0.0, 0.0), wait=wait
            )
            guest_route[guest_index] = replace(
                guest_route[guest_index], velocity=(0.0, 0.0), wait=wait
            )
            routes = list(solution.routes)
            routes[host] = tuple(host_route)
            routes[guest] = tuple(guest_route)
            yield Solution(tuple(routes))


def _invitation_candidates(runner: "Runner", solution: Solution):
    radius = 0.9 * runner.config.comm_range
    offsets = (-0.25, 0.0, 0.25)
    durations = (0.5, 1.0, 1.5)
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
            for duration_factor in durations:
                host_route = list(solution.routes[host])
                host_route[host_index] = replace(
                    host_visit,
                    velocity=(0.0, 0.0),
                    wait=duration_factor * runner.config.handshake_time,
                )
                guest_route = list(solution.routes[guest])
                guest_route.insert(
                    max(1, guest_index),
                    Visit(fresh_id(solution, "invite"), "FREE", point),
                )
                routes = list(solution.routes)
                routes[host] = tuple(host_route)
                routes[guest] = tuple(guest_route)
                yield Solution(tuple(routes))


def _retiming_candidates(runner: "Runner", solution: Solution):
    for agent, route in enumerate(solution.routes):
        for visit_index, visit in enumerate(route[:-1]):
            if visit.kind != "FREE" and visit.wait <= 0:
                continue
            for step in runner.config.wait_steps:
                updated = replace(
                    visit,
                    velocity=(0.0, 0.0),
                    wait=max(0.0, visit.wait + step),
                )
                changed = list(route)
                changed[visit_index] = updated
                yield edited(solution, agent, changed)


def _candidate_set(runner: "Runner", solution: Solution) -> list[Solution]:
    candidates = {}
    generators = (
        _link_candidates(runner, solution),
        _invitation_candidates(runner, solution),
        _retiming_candidates(runner, solution),
    )
    for generator in generators:
        for candidate in generator:
            candidates.setdefault(candidate.key, candidate)
    values = list(candidates.values())
    runner.rng.shuffle(values)
    return values[: runner.config.neighborhood_candidates]


def repair_communication(runner: "Runner", solution: Solution) -> Solution:
    """Run at most three exact best-improvement CV repair rounds."""
    if solution.evaluation.comm_violation <= runner.config.numerical_tolerance:
        return solution
    runner.counts["communication_repair_calls"] += 1
    initial_cv = solution.evaluation.comm_violation
    current = solution
    reduced = False
    for round_index in range(runner.config.communication_repair_rounds):
        scored = []
        for candidate in _candidate_set(runner, current):
            if runner.exhausted():
                break
            evaluated = runner.evaluate(candidate, "communication_repair")
            if evaluated is not None:
                scored.append(evaluated)
        if not scored:
            break
        best = min(
            scored,
            key=lambda candidate: (
                candidate.evaluation.comm_violation,
                -candidate.evaluation.reward,
                candidate.objectives[1],
                repr(candidate.key),
            ),
        )
        if best.evaluation.comm_violation >= current.evaluation.comm_violation:
            break
        reduced = True
        current = best
        runner.repair_history.append(
            {
                "round": round_index + 1,
                "before_cv": initial_cv if round_index == 0 else None,
                "after_cv": current.evaluation.comm_violation,
            }
        )
        if current.evaluation.comm_violation <= runner.config.numerical_tolerance:
            runner.counts["communication_repair_zeroed"] += 1
            break
    if reduced:
        runner.counts["communication_repair_reduced"] += 1
    return current
