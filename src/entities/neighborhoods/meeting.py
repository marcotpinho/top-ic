"""Sample stopped links, waits, and free rendezvous edits; implements N7–N10."""

from collections.abc import Iterator
from dataclasses import replace
from itertools import combinations, product
from math import hypot
from random import Random

from ...config import Config, Problem
from ...solution import Meeting, Solution, Visit
from .common import edited, fresh_id, in_workspace, normalize, sample_candidates

name = "meeting"


def _distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return hypot(left[0] - right[0], left[1] - right[1])


def _link_proposals(solution: Solution, config: Config):
    existing = set(solution.meetings)
    for agent, other_agent in combinations(range(len(solution.routes)), 2):
        count = 0
        for left, right in product(
            solution.routes[agent], solution.routes[other_agent]
        ):
            link = Meeting(left.id, right.id)
            if (
                left.velocity == right.velocity == (0.0, 0.0)
                and _distance(left.position, right.position) <= config.comm_range
                and link not in existing
            ):
                yield link
                count += 1
                if count >= config.meeting_link_limit:
                    break


def _free_slots(route, config: Config) -> tuple[int, ...]:
    slots = range(1, len(route))
    return tuple(slots)[: config.meeting_slot_limit]


def _meeting_point(
    solution: Solution, agent: int, other_agent: int, fraction: float, config: Config
) -> tuple[float, float]:
    bottleneck = (
        solution.evaluation.communication.bottleneck
        if solution.evaluation and solution.evaluation.communication
        else None
    )
    if bottleneck and set(bottleneck[:2]) == {agent, other_agent}:
        time = bottleneck[2]
        trajectories = solution.evaluation.trajectories
        host = trajectories[agent].state(time).position
        guest = trajectories[other_agent].state(time).position
    else:
        host = solution.routes[agent][len(solution.routes[agent]) // 2].position
        guest = solution.routes[other_agent][
            len(solution.routes[other_agent]) // 2
        ].position
    distance = _distance(host, guest)
    if distance == 0:
        return host
    invite = min(
        distance / 2, fraction * config.invite_radius_fraction * config.comm_range
    )
    return tuple(
        host[axis] + (guest[axis] - host[axis]) * invite / distance for axis in (0, 1)
    )


def _free_pair_proposals(solution: Solution, config: Config):
    for agent, other_agent in combinations(range(len(solution.routes)), 2):
        if any(
            sum(visit.kind == "FREE" for visit in solution.routes[member])
            >= config.max_free_waypoints
            for member in (agent, other_agent)
        ):
            continue
        for fraction in config.rendezvous_radius_fractions:
            point = _meeting_point(solution, agent, other_agent, fraction, config)
            if not in_workspace(point, config.waypoint_workspace):
                continue
            for visit_index, partner_index in product(
                _free_slots(solution.routes[agent], config),
                _free_slots(solution.routes[other_agent], config),
            ):
                yield agent, visit_index, other_agent, partner_index, point


def _insert_free_pair(solution: Solution, proposal) -> Solution:
    agent, visit_index, other_agent, partner_index, point = proposal
    routes = [list(route) for route in solution.routes]
    left_id = fresh_id(solution, "relay-left")
    right_id = fresh_id(solution, "relay-right")
    routes[agent].insert(visit_index, Visit(left_id, "FREE", point))
    routes[other_agent].insert(partner_index, Visit(right_id, "FREE", point))
    return normalize(routes, (*solution.meetings, Meeting(left_id, right_id)))


def _wait_proposals(solution: Solution, config: Config):
    for agent, route in enumerate(solution.routes):
        for visit_index, visit in enumerate(route[:-1]):
            if visit.velocity == (0.0, 0.0):
                for step in config.wait_steps:
                    yield agent, visit_index, step


def _free_move_proposals(solution: Solution, config: Config):
    for agent, route in enumerate(solution.routes):
        for visit_index, visit in enumerate(route[1:-1], 1):
            if visit.kind == "FREE":
                for axis, sign, step in product((0, 1), (-1, 1), config.waypoint_steps):
                    yield agent, visit_index, axis, sign, step


def _move_free(solution: Solution, proposal, config: Config) -> Solution | None:
    agent, visit_index, axis, sign, step = proposal
    routes = [list(route) for route in solution.routes]
    visit = routes[agent][visit_index]
    point = list(visit.position)
    point[axis] += sign * step
    if not in_workspace(point, config.waypoint_workspace):
        return None
    routes[agent][visit_index] = replace(visit, position=tuple(point))
    partners = {
        link.right if link.left == visit.id else link.left
        for link in solution.meetings
        if visit.id in (link.left, link.right)
    }
    for other_agent, partner_route in enumerate(routes):
        if other_agent == agent:
            continue
        for partner_index, partner in enumerate(partner_route):
            if partner.id in partners and partner.kind == "FREE":
                other_point = list(partner.position)
                other_point[axis] += sign * step
                if in_workspace(other_point, config.waypoint_workspace):
                    partner_route[partner_index] = replace(
                        partner, position=tuple(other_point)
                    )
    return normalize(routes, solution.meetings)


def generate(
    solution: Solution, problem: Problem, config: Config, rng: Random
) -> Iterator[Solution]:
    """Sample stopped rendezvous decisions and reevaluate handshake (eq. 10)."""
    if len(solution.routes) < 2:
        return
    cap = config.neighborhood_candidates
    for link in sample_candidates(_link_proposals(solution, config), rng, cap):
        yield normalize(solution.routes, (*solution.meetings, link))
    proposals = _free_pair_proposals(solution, config)
    for proposal in sample_candidates(proposals, rng, cap):
        yield _insert_free_pair(solution, proposal)
    for agent, visit_index, step in sample_candidates(
        _wait_proposals(solution, config), rng, cap
    ):
        route = list(solution.routes[agent])
        route[visit_index] = replace(
            route[visit_index], wait=route[visit_index].wait + step
        )
        yield edited(solution, agent, route)
    for proposal in sample_candidates(_free_move_proposals(solution, config), rng, cap):
        candidate = _move_free(solution, proposal, config)
        if candidate is not None:
            yield candidate
