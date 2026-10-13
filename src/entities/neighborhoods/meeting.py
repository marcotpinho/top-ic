"""Sample stopped links, waits, and gap-targeted free rendezvous edits; implements N7–N10."""

from collections.abc import Iterator
from dataclasses import replace
from itertools import combinations, product
from math import hypot
from random import Random

from ...config import Config, Problem
from ...solution import Meeting, Solution, Visit
from .common import edited, in_workspace, normalize, sample_candidates

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


def _free_capacity(solution: Solution, config: Config, agents) -> int:
    """Return how many more FREE visits every listed agent can still take."""
    return min(
        config.max_free_waypoints
        - sum(visit.kind == "FREE" for visit in solution.routes[member])
        for member in agents
    )


def _gap_targets(solution: Solution, agent: int, other_agent: int) -> tuple:
    """Return times inside the pair's longest no-contact gap.

    The sweep's bottleneck time is where peak age is reached, i.e. the end of
    the gap; targeting the gap interior splits it instead.
    """
    communication = solution.evaluation.communication
    bottleneck = communication.bottleneck if communication else None
    if not bottleneck or set(bottleneck[:2]) != {agent, other_agent}:
        return ()
    end = bottleneck[2]
    pair = tuple(sorted((agent, other_agent)))
    start = max(
        (
            right
            for record in communication.contacts
            if tuple(record.agents) == pair
            for _, right in record.effective
            if right <= end
        ),
        default=0.0,
    )
    if end <= start:
        return ()
    return tuple(start + (end - start) * share for share in (1 / 2, 1 / 3, 2 / 3))


def _aligned_slot(solution: Solution, agent: int, time: float) -> int:
    """Return the insertion index whose leg the agent flies at the given time."""
    arrivals = [times[0] for times in solution.evaluation.visit_times[agent]]
    for index in range(1, len(arrivals)):
        if time < arrivals[index]:
            return index
    return len(arrivals) - 1


def _leg_midpoint(solution: Solution, agent: int, time: float) -> float:
    """Return the middle of the leg flown at a time, so a dip can span that leg."""
    times = solution.evaluation.visit_times[agent]
    index = _aligned_slot(solution, agent, time)
    return (times[index - 1][1] + times[index][0]) / 2


def _target_variants(solution: Solution, agent: int, time: float) -> tuple:
    """Return the raw target and the host's leg midpoint around it."""
    snapped = _leg_midpoint(solution, agent, time)
    return (time,) if abs(snapped - time) < 1e-9 else (time, snapped)


def _paired_points(solution: Solution, agent: int, other_agent: int, time, fraction, config):
    """Move both agents' positions at a time toward each other until fraction·R apart."""
    trajectories = solution.evaluation.trajectories
    host = trajectories[agent].state(time).position
    guest = trajectories[other_agent].state(time).position
    distance = _distance(host, guest)
    if distance == 0:
        return host, guest
    move = max(0.0, (distance - fraction * config.comm_range) / 2) / distance
    left = tuple(host[axis] + (guest[axis] - host[axis]) * move for axis in (0, 1))
    right = tuple(guest[axis] + (host[axis] - guest[axis]) * move for axis in (0, 1))
    return left, right


def _pair_at(solution, agent, other_agent, time, fraction, config):
    left, right = _paired_points(solution, agent, other_agent, time, fraction, config)
    if not (
        in_workspace(left, config.waypoint_workspace)
        and in_workspace(right, config.waypoint_workspace)
    ):
        return None
    return (
        _aligned_slot(solution, agent, time),
        left,
        _aligned_slot(solution, other_agent, time),
        right,
    )


def _gap_pair_proposals(solution: Solution, config: Config):
    """Yield one rendezvous inside the longest gap, linked (stopped) or fly-through."""
    for agent, other_agent in combinations(range(len(solution.routes)), 2):
        if _free_capacity(solution, config, (agent, other_agent)) < 1:
            continue
        times = {
            variant
            for target in _gap_targets(solution, agent, other_agent)
            for variant in _target_variants(solution, agent, target)
        }
        for time, fraction in product(sorted(times), config.rendezvous_radius_fractions):
            pair = _pair_at(solution, agent, other_agent, time, fraction, config)
            if pair is not None:
                for linked in (False, True):
                    yield agent, other_agent, (pair,), linked


def _spread_pair_proposals(solution: Solution, config: Config):
    """Yield k unlinked rendezvous evenly spaced over the mission, k >= 2.

    Each spread is also proposed snapped to the host's leg midpoints, so the
    lateral dips span whole task-to-task legs instead of crowding a task.
    """
    horizon = max(solution.evaluation.completion_times, default=0.0)
    for agent, other_agent in combinations(range(len(solution.routes)), 2):
        capacity = _free_capacity(solution, config, (agent, other_agent))
        for count, fraction, snap in product(
            range(2, capacity + 1), config.rendezvous_radius_fractions, (False, True)
        ):
            times = [horizon * j / (count + 1) for j in range(1, count + 1)]
            if snap:
                times = [_leg_midpoint(solution, agent, time) for time in times]
            pairs = tuple(
                _pair_at(solution, agent, other_agent, time, fraction, config)
                for time in times
            )
            if None not in pairs:
                yield agent, other_agent, pairs, False


def _midpoint_pair_proposals(solution: Solution, config: Config):
    """Fallback for unevaluated solutions: route-midpoint invitations, early slots."""
    for agent, other_agent in combinations(range(len(solution.routes)), 2):
        if _free_capacity(solution, config, (agent, other_agent)) < 1:
            continue
        for fraction in config.rendezvous_radius_fractions:
            point = _meeting_point(solution, agent, other_agent, fraction, config)
            if not in_workspace(point, config.waypoint_workspace):
                continue
            for visit_index, partner_index in product(
                _free_slots(solution.routes[agent], config),
                _free_slots(solution.routes[other_agent], config),
            ):
                pair = (visit_index, point, partner_index, point)
                yield agent, other_agent, (pair,), True


def _free_pair_proposals(solution: Solution, config: Config):
    evaluation = solution.evaluation
    if evaluation is None or not evaluation.visit_times or not evaluation.trajectories:
        yield from _midpoint_pair_proposals(solution, config)
        return
    yield from _gap_pair_proposals(solution, config)
    yield from _spread_pair_proposals(solution, config)


def _insert_free_pair(solution: Solution, proposal) -> Solution:
    """Insert FREE pairs (in time order) and optionally link each pair."""
    agent, other_agent, pairs, linked = proposal
    routes = [list(route) for route in solution.routes]
    used = {visit.id for route in solution.routes for visit in route}
    meetings = list(solution.meetings)
    # Later slots first so earlier insertion indices stay valid.
    for visit_index, left, partner_index, right in reversed(pairs):
        left_id, right_id = (
            _unused(used, f"relay-{side}") for side in ("left", "right")
        )
        routes[agent].insert(visit_index, Visit(left_id, "FREE", left))
        routes[other_agent].insert(partner_index, Visit(right_id, "FREE", right))
        if linked:
            meetings.append(Meeting(left_id, right_id))
    return normalize(routes, tuple(meetings))


def _unused(used: set[str], prefix: str) -> str:
    index = 0
    while f"{prefix}:{index}" in used:
        index += 1
    used.add(f"{prefix}:{index}")
    return f"{prefix}:{index}"


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
