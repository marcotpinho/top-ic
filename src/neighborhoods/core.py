"""Lazy occurrence-level KOP neighborhoods with deterministic enumeration."""

from dataclasses import replace
from math import hypot
from ..config import velocity_menu
from ..solution import Solution, Visit, Meeting
from ..velocity_dp import refine_route_velocities

from .common import (
    normalize,
    fresh_id,
    edited,
    in_workspace,
    segment_projection,
    reached_task_ids,
)
from .registry import COMM_NEIGHBORHOODS


def _detour(before, point, after):
    from math import hypot

    return (
        hypot(point[0] - before[0], point[1] - before[1])
        + hypot(after[0] - point[0], after[1] - point[1])
        - hypot(after[0] - before[0], after[1] - before[1])
    )


def _round_robin(streams):
    streams = list(streams)
    while streams:
        remaining = []
        for stream in streams:
            try:
                yield next(stream)
            except StopIteration:
                continue
            remaining.append(stream)
        streams = remaining


def neighbors(
    solution, problem, config, family, agent_order=None, pair_filter=None, rng=None
):
    if family == "velocity_dp":
        forced = {
            identity
            for pair in solution.meetings
            for identity in (pair.left, pair.right)
        }
        refined = []
        changed = []
        for m, route in enumerate(solution.routes):
            candidate = refine_route_velocities(
                route, problem.limits[m], config, forced
            )
            refined.append(candidate if candidate is not None else route)
            if candidate is not None and candidate != route:
                changed.append(m)
                yield edited(solution, m, candidate)
        if len(changed) > 1:
            yield normalize(refined, solution.meetings)
        return
    if family in COMM_NEIGHBORHOODS:
        yield from communication_neighbors(
            solution, problem, config, family, pair_filter, rng
        )
        return
    reached = reached_task_ids(solution)
    order = (
        tuple(range(len(solution.routes)))
        if agent_order is None
        else tuple(agent_order)
    )
    if family in ("remove", "replace", "assignment"):
        for duplicated_only in (True, False):
            yield from _round_robin(
                _agent_neighbors(
                    solution, problem, config, family, m, reached, duplicated_only
                )
                for m in order
            )
    else:
        yield from _round_robin(
            _agent_neighbors(solution, problem, config, family, m, reached)
            for m in order
        )


def _agent_neighbors(
    solution, problem, config, family, m, reached, duplicated_only=None
):
    route = solution.routes[m]
    menu = velocity_menu(problem.limits[m], config)
    forced = {
        identity for pair in solution.meetings for identity in (pair.left, pair.right)
    }
    others = {
        v.task_id
        for n, other in enumerate(solution.routes)
        if n != m
        for v in other
        if v.kind == "TASK"
    }
    available = [task for task in problem.tasks if task.id not in reached]
    if family == "insert":
        ranked = []
        for task in available:
            choices = sorted(
                (_detour(route[k - 1].position, task.position, route[k].position), k)
                for k in range(1, len(route))
            )[:2]
            for cost, k in choices:
                ranked.append((cost, task.id, k, task))
        for _, _, k, task in sorted(ranked):
            for velocity in ((0.0, 0.0),) if config.mode == "team_kop_icc" else menu:
                visit = Visit(
                    fresh_id(solution, "task"), "TASK", task.position, velocity, task.id
                )
                yield edited(solution, m, route[:k] + (visit,) + route[k:])
    elif family == "remove":
        positions = [
            k
            for k in range(1, len(route) - 1)
            if route[k].kind == "TASK"
            and route[k].id not in forced
            and (
                duplicated_only is None
                or (route[k].task_id in others) == duplicated_only
            )
        ]
        for k in positions:
            yield edited(solution, m, route[:k] + route[k + 1 :])
    elif family == "replace":
        positions = [
            k
            for k in range(1, len(route) - 1)
            if route[k].kind == "TASK"
            and route[k].id not in forced
            and (
                duplicated_only is None
                or (route[k].task_id in others) == duplicated_only
            )
        ]
        for k in positions:
            nearby = sorted(
                available,
                key=lambda t: (
                    _detour(route[k - 1].position, t.position, route[k + 1].position),
                    t.id,
                ),
            )[:5]
            for task in nearby:
                for velocity in (
                    ((0.0, 0.0),) if config.mode == "team_kop_icc" else menu
                ):
                    visit = Visit(
                        fresh_id(solution, "task"),
                        "TASK",
                        task.position,
                        velocity,
                        task.id,
                    )
                    yield edited(solution, m, route[:k] + (visit,) + route[k + 1 :])
    elif family == "reorder":
        interior = route[1:-1]
        for start in range(len(interior)):
            for width in range(1, min(3, len(interior) - start) + 1):
                chunk = interior[start : start + width]
                if any(v.id in forced for v in chunk):
                    continue
                rest = interior[:start] + interior[start + width :]
                for target in range(max(0, start - 5), min(len(rest), start + 5) + 1):
                    if target == start:
                        continue
                    yield edited(
                        solution,
                        m,
                        (route[0],)
                        + rest[:target]
                        + chunk
                        + rest[target:]
                        + (route[-1],),
                    )
        for i in range(1, len(route) - 1):
            for j in range(i + 2, len(route)):
                if any(v.id in forced for v in route[i:j]):
                    continue
                yield edited(
                    solution, m, route[:i] + tuple(reversed(route[i:j])) + route[j:]
                )
    elif family == "velocity":
        for k in range(1, len(route) - 1):
            for velocity in menu:
                if velocity != route[k].velocity:
                    yield edited(
                        solution,
                        m,
                        route[:k]
                        + (replace(route[k], velocity=velocity, wait=0.0),)
                        + route[k + 1 :],
                    )
        for k, v in enumerate(route[:-1]):
            if v.wait > 0:
                yield edited(
                    solution, m, route[:k] + (replace(v, wait=0.0),) + route[k + 1 :]
                )
    elif family == "assignment":
        positions = [
            k
            for k in range(1, len(route) - 1)
            if route[k].kind == "TASK"
            and route[k].id not in forced
            and (
                duplicated_only is None
                or (route[k].task_id in others) == duplicated_only
            )
        ]
        own_ids = {v.task_id for v in route if v.kind == "TASK"}
        for n, other in enumerate(solution.routes):
            if n == m:
                continue
            target_ids = {v.task_id for v in other if v.kind == "TASK"}
            target_menu = (
                ((0.0, 0.0),)
                if config.mode == "team_kop_icc"
                else velocity_menu(problem.limits[n], config)
            )
            own_menu = ((0.0, 0.0),) if config.mode == "team_kop_icc" else menu
            for k in positions:
                visit = route[k]
                if visit.task_id not in target_ids:
                    choices = sorted(
                        (
                            _detour(
                                other[j - 1].position, visit.position, other[j].position
                            ),
                            j,
                        )
                        for j in range(1, len(other))
                    )[:2]
                    for _, j in choices:
                        for velocity in target_menu:
                            routes = list(solution.routes)
                            routes[m] = route[:k] + route[k + 1 :]
                            routes[n] = (
                                other[:j]
                                + (replace(visit, velocity=velocity, wait=0.0),)
                                + other[j:]
                            )
                            yield normalize(routes, solution.meetings)
                if m < n:
                    for j in range(1, len(other) - 1):
                        if other[j].kind != "TASK" or other[j].id in forced:
                            continue
                        if other[j].task_id in own_ids or visit.task_id in target_ids:
                            continue
                        for vm in own_menu:
                            for vn in target_menu:
                                routes = list(solution.routes)
                                routes[m] = (
                                    route[:k]
                                    + (replace(other[j], velocity=vm, wait=0.0),)
                                    + route[k + 1 :]
                                )
                                routes[n] = (
                                    other[:j]
                                    + (replace(visit, velocity=vn, wait=0.0),)
                                    + other[j + 1 :]
                                )
                                yield normalize(routes, solution.meetings)
            if m < n and duplicated_only is not True:
                cut_pairs = []
                for i in range(1, len(route)):
                    tail = route[i:-1]
                    if any(v.kind == "FREE" or v.id in forced for v in tail):
                        continue
                    for j in range(1, len(other)):
                        other_tail = other[j:-1]
                        if any(v.kind == "FREE" or v.id in forced for v in other_tail):
                            continue
                        cost = hypot(
                            route[i].position[0] - other[j].position[0],
                            route[i].position[1] - other[j].position[1],
                        )
                        cut_pairs.append((cost, i, j))
                for _, i, j in sorted(cut_pairs)[:10]:
                    routes = list(solution.routes)
                    routes[m] = (
                        route[:i]
                        + tuple(
                            replace(v, velocity=(0.0, 0.0), wait=0.0)
                            for v in other[j:-1]
                        )
                        + (route[-1],)
                    )
                    routes[n] = (
                        other[:j]
                        + tuple(
                            replace(v, velocity=(0.0, 0.0), wait=0.0)
                            for v in route[i:-1]
                        )
                        + (other[-1],)
                    )
                    yield normalize(routes, solution.meetings)


def communication_neighbors(
    solution, problem, config, family, pair_filter=None, rng=None
):
    if config.mode != "team_kop_icc":
        return
    if family == "excursion":
        # Shared task/start/end anchors may occur at different route indices.
        def anchor_key(v):
            return (v.kind, v.task_id if v.kind == "TASK" else v.position)

        forced = {
            identity
            for pair in solution.meetings
            for identity in (pair.left, pair.right)
        }
        for scout, route in enumerate(solution.routes):
            for follower, other in enumerate(solution.routes):
                if scout == follower:
                    continue
                if (
                    pair_filter is not None
                    and tuple(sorted((scout, follower))) != pair_filter
                ):
                    continue
                for left, anchor in enumerate(route[:-2]):
                    for other_left, other_anchor in enumerate(other[:-2]):
                        if anchor_key(anchor) != anchor_key(other_anchor):
                            continue
                        for other_right in range(
                            other_left + 2, min(len(other), other_left + 7)
                        ):
                            inside = other[other_left + 1 : other_right]
                            if any(v.kind != "TASK" or v.id in forced for v in inside):
                                continue
                            other_reunion = other[other_right]
                            for right in range(left + 1, len(route)):
                                reunion = route[right]
                                if anchor_key(reunion) != anchor_key(other_reunion):
                                    continue
                                routes = list(solution.routes)
                                routes[follower] = (
                                    other[: other_left + 1] + other[other_right:]
                                )
                                moving = normalize(routes, solution.meetings)
                                reached = {
                                    v.task_id
                                    for r in solution.routes
                                    for v in r
                                    if v.kind == "TASK"
                                }
                                available = [
                                    task
                                    for task in problem.tasks
                                    if task.reward > 0 and task.id not in reached
                                ]
                                shortcut = sorted(
                                    available,
                                    key=lambda task: (
                                        _detour(
                                            other_anchor.position,
                                            task.position,
                                            other_reunion.position,
                                        ),
                                        task.id,
                                    ),
                                )[:2]
                                if shortcut:
                                    changed = list(moving.routes)
                                    amended = list(changed[follower])
                                    for task in shortcut:
                                        visit = Visit(
                                            fresh_id(
                                                normalize(changed), "excursion-task"
                                            ),
                                            "TASK",
                                            task.position,
                                            (0.0, 0.0),
                                            task.id,
                                        )
                                        amended.insert(other_left + 1, visit)
                                        changed[follower] = tuple(amended)
                                        yield normalize(changed, moving.meetings)
                                yield moving
                                if (
                                    reunion.kind == "END"
                                    or reunion.id in forced
                                    or other_reunion.id in forced
                                ):
                                    continue
                                stopped = list(routes)
                                stopped[scout] = (
                                    route[:right]
                                    + (replace(reunion, velocity=(0.0, 0.0)),)
                                    + route[right + 1 :]
                                )
                                target = stopped[follower]
                                stopped[follower] = (
                                    target[: other_left + 1]
                                    + (
                                        replace(
                                            target[other_left + 1], velocity=(0.0, 0.0)
                                        ),
                                    )
                                    + target[other_left + 2 :]
                                )
                                yield normalize(
                                    stopped,
                                    solution.meetings
                                    + (Meeting(reunion.id, other_reunion.id),),
                                )
    elif family == "duplicate_rendezvous":
        if config.max_free_waypoints == 0:
            return
        # Rank redundant visits by geometric detour as an enumeration heuristic.
        # Actual cost and communication are always recomputed by the evaluator.
        candidates = []
        for m, route in enumerate(solution.routes):
            if pair_filter is not None and m not in pair_filter:
                continue
            if sum(v.kind == "FREE" for v in route) >= config.max_free_waypoints:
                continue
            for k, visit in enumerate(route[1:-1], 1):
                if visit.kind != "TASK":
                    continue
                all_partners = [
                    (n, j, other)
                    for n, other_route in enumerate(solution.routes)
                    if n != m
                    for j, other in enumerate(other_route[1:-1], 1)
                    if other.kind == "TASK" and other.task_id == visit.task_id
                ]
                partners = [
                    p
                    for p in all_partners
                    if pair_filter is None or tuple(sorted((m, p[0]))) == pair_filter
                ]
                if not partners:
                    continue
                before = route[k - 1].position
                after = route[k + 1].position
                direction = (after[0] - before[0], after[1] - before[1])
                length2 = direction[0] ** 2 + direction[1] ** 2
                if length2 == 0:
                    continue
                fraction = max(
                    0.0,
                    min(
                        1.0,
                        sum(
                            (visit.position[d] - before[d]) * direction[d]
                            for d in range(2)
                        )
                        / length2,
                    ),
                )
                projection = tuple(
                    before[d] + fraction * direction[d] for d in range(2)
                )
                distance = hypot(*(projection[d] - visit.position[d] for d in range(2)))
                if distance <= config.geometry_tolerance:
                    continue
                detour = (
                    hypot(*(before[d] - visit.position[d] for d in range(2)))
                    + hypot(*(after[d] - visit.position[d] for d in range(2)))
                    - length2**0.5
                )
                home = tuple(sorted((m, min(n for n, _, _ in all_partners))))
                candidates.append(
                    (-detour, m, k, visit, partners, projection, distance, home)
                )
        for _, m, k, visit, partners, projection, distance, home in sorted(
            candidates, key=lambda row: row[: config.meeting_slot_limit]
        ):
            route = solution.routes[m]
            seen_points = set()
            for radius_fraction in config.rendezvous_radius_fractions:
                offset = min(distance, radius_fraction * config.comm_range)
                point = tuple(
                    visit.position[d]
                    + (projection[d] - visit.position[d]) * offset / distance
                    for d in range(2)
                )
                if point in seen_points:
                    continue
                seen_points.add(point)
                if not in_workspace(point, config.waypoint_workspace):
                    continue
                free = replace(
                    visit,
                    kind="FREE",
                    position=point,
                    velocity=(0.0, 0.0),
                    task_id=None,
                    wait=0.0,
                )
                routes = list(solution.routes)
                routes[m] = route[:k] + (free,) + route[k + 1 :]
                # Permit natural contacts as well as an explicit stopped meeting.
                if pair_filter is None or pair_filter == home:
                    yield normalize(routes, solution.meetings)
                for n, j, other in partners:
                    if any(
                        {p.left, p.right} == {visit.id, other.id}
                        for p in solution.meetings
                    ):
                        continue
                    coordinated = list(routes)
                    partner_route = solution.routes[n]
                    coordinated[n] = (
                        partner_route[:j]
                        + (replace(other, velocity=(0.0, 0.0), wait=0.0),)
                        + partner_route[j + 1 :]
                    )
                    yield normalize(
                        coordinated, solution.meetings + (Meeting(visit.id, other.id),)
                    )
    elif family == "wait":
        for m, route in enumerate(solution.routes):
            for k, v in enumerate(route[:-1]):
                if k == 0 and problem.initial_velocities[m] != (0.0, 0.0):
                    continue
                for step in config.wait_steps:
                    for wait in sorted(
                        set([0.0, v.wait + step, max(0.0, v.wait - step)])
                    ):
                        changed = replace(v, velocity=(0.0, 0.0), wait=wait)
                        if changed != v:
                            yield edited(
                                solution, m, route[:k] + (changed,) + route[k + 1 :]
                            )
    elif family in ("free_remove", "unlink"):
        owners = {v.id: m for m, route in enumerate(solution.routes) for v in route}
        for pair in solution.meetings:
            if (
                pair_filter is not None
                and tuple(sorted((owners[pair.left], owners[pair.right])))
                != pair_filter
            ):
                continue
            yield normalize(
                solution.routes, tuple(p for p in solution.meetings if p != pair)
            )
        for m, route in enumerate(solution.routes):
            if pair_filter is not None:
                if m not in pair_filter:
                    continue
                home = tuple(sorted((m, 0 if m else 1)))
                if pair_filter != home:
                    continue
            for k, v in enumerate(route[1:-1], 1):
                if v.kind == "FREE":
                    yield edited(solution, m, route[:k] + route[k + 1 :])
            if family == "unlink":
                for k, v in enumerate(route[:-1]):
                    if v.wait > 0:
                        yield edited(
                            solution,
                            m,
                            route[:k] + (replace(v, wait=0.0),) + route[k + 1 :],
                        )
    elif family == "free_move":
        positions = {
            v.id: (m, k, v)
            for m, r in enumerate(solution.routes)
            for k, v in enumerate(r)
        }
        groups = [(v.id,) for r in solution.routes for v in r if v.kind == "FREE"]
        groups.extend(
            (p.left, p.right)
            for p in solution.meetings
            if all(positions[x][2].kind == "FREE" for x in (p.left, p.right))
        )
        for group in groups:
            for step in config.waypoint_steps:
                for dx, dy in ((step, 0), (-step, 0), (0, step), (0, -step)):
                    routes = [list(r) for r in solution.routes]
                    allowed = True
                    for identity in group:
                        m, k, v = positions[identity]
                        point = (v.position[0] + dx, v.position[1] + dy)
                        if config.waypoint_workspace is not None:
                            xmin, xmax, ymin, ymax = config.waypoint_workspace
                            if not (
                                xmin <= point[0] <= xmax and ymin <= point[1] <= ymax
                            ):
                                allowed = False
                                break
                        routes[m][k] = replace(v, position=point)
                    if allowed:
                        yield normalize(routes, solution.meetings)
    elif family == "meeting":
        ev = solution.evaluation
        target = 0.0
        bottleneck = ev.communication.bottleneck if ev and ev.communication else None
        if ev:
            target = max(
                0.0,
                bottleneck[2] - config.handshake_time
                if bottleneck
                else max(ev.completion_times) / 2,
            )

        def at(m, k):
            return ev.visit_times[m][k][0] if ev else 0.0

        def slots(m):
            route = solution.routes[m]
            return sorted(
                range(1, len(route)), key=lambda k: (abs(at(m, k - 1) - target), k)
            )[: config.meeting_slot_limit]

        # Retiming is useful only at a communication structure. A stopped
        # meeting endpoint can wait less or more; other waits go to unlink.
        positions = {
            v.id: (m, k) for m, r in enumerate(solution.routes) for k, v in enumerate(r)
        }
        for pair in solution.meetings:
            if (
                pair_filter is not None
                and tuple(sorted((positions[pair.left][0], positions[pair.right][0])))
                != pair_filter
            ):
                continue
            for identity in (pair.left, pair.right):
                if identity not in positions:
                    continue
                m, k = positions[identity]
                route = solution.routes[m]
                v = route[k]
                for step in config.wait_steps:
                    for wait in (max(0.0, v.wait - step), v.wait + step):
                        if wait != v.wait:
                            yield edited(
                                solution,
                                m,
                                route[:k]
                                + (replace(v, velocity=(0.0, 0.0), wait=wait),)
                                + route[k + 1 :],
                            )
        pairs = (
            [pair_filter]
            if pair_filter is not None
            else [
                (m, n)
                for m in range(len(solution.routes))
                for n in range(m + 1, len(solution.routes))
            ]
        )
        if rng is not None:
            rng.shuffle(pairs)
        if bottleneck:
            focus = tuple(sorted(bottleneck[:2]))
            pairs.sort(key=lambda p: p != focus)
        for m, n in pairs:
            route, other = solution.routes[m], solution.routes[n]
            # Existing visits can be linked without adding geometry.
            links = []
            for k, a in enumerate(route[:-1]):
                if k == 0 and a.velocity != (0.0, 0.0):
                    continue
                for j, b in enumerate(other[:-1]):
                    if j == 0 and b.velocity != (0.0, 0.0):
                        continue
                    if (
                        hypot(
                            a.position[0] - b.position[0], a.position[1] - b.position[1]
                        )
                        > config.comm_range
                    ):
                        continue
                    pair = Meeting(a.id, b.id)
                    if pair in solution.meetings:
                        continue
                    links.append(
                        (abs(at(m, k) - target) + abs(at(n, j) - target), k, j, pair)
                    )
            for _, k, j, pair in sorted(links)[: config.meeting_link_limit]:
                routes = [list(r) for r in solution.routes]
                routes[m][k] = replace(route[k], velocity=(0.0, 0.0))
                routes[n][j] = replace(other[j], velocity=(0.0, 0.0))
                yield normalize(routes, solution.meetings + (pair,))
            # A stopped host at a useful task can invite the other agent to
            # a deterministic, range-clipped projection onto its route.
            for host, guest in ((m, n), (n, m)):
                host_route = solution.routes[host]
                guest_route = solution.routes[guest]
                if (
                    sum(v.kind == "FREE" for v in guest_route)
                    >= config.max_free_waypoints
                ):
                    continue
                host_indices = sorted(
                    range(len(host_route) - 1),
                    key=lambda k: (abs(at(host, k) - target), k),
                )[: config.meeting_slot_limit]
                for hk in host_indices:
                    hv = host_route[hk]
                    if hk == 0 and hv.velocity != (0.0, 0.0):
                        continue
                    if any(
                        gv.velocity == (0.0, 0.0)
                        and hypot(
                            gv.position[0] - hv.position[0],
                            gv.position[1] - hv.position[1],
                        )
                        <= config.comm_range
                        and abs(at(guest, gj) - at(host, hk)) <= config.handshake_time
                        for gj, gv in enumerate(guest_route[:-1])
                    ):
                        continue

                    # Favor guest segments that are near range at the
                    # bottleneck time, including segments just outside R.
                    def guest_rank(gk):
                        a, b = guest_route[gk - 1].position, guest_route[gk].position
                        direction = (b[0] - a[0], b[1] - a[1])
                        length2 = sum(x * x for x in direction)
                        fraction = (
                            max(
                                0.0,
                                min(
                                    1.0,
                                    sum(
                                        (hv.position[d] - a[d]) * direction[d]
                                        for d in range(2)
                                    )
                                    / length2,
                                ),
                            )
                            if length2
                            else 0.0
                        )
                        projection = tuple(
                            a[d] + fraction * direction[d] for d in range(2)
                        )
                        gap = max(
                            0.0,
                            hypot(
                                projection[0] - hv.position[0],
                                projection[1] - hv.position[1],
                            )
                            - config.comm_range,
                        )
                        return (
                            gap / max(config.comm_range, config.geometry_tolerance)
                            + abs(at(guest, gk - 1) - target)
                            / max(config.recurrence_bound, 1.0),
                            gk,
                        )

                    for gk in sorted(range(1, len(guest_route)), key=guest_rank)[
                        : config.meeting_slot_limit
                    ]:
                        before, after = (
                            guest_route[gk - 1].position,
                            guest_route[gk].position,
                        )
                        direction = (after[0] - before[0], after[1] - before[1])
                        length2 = sum(x * x for x in direction)
                        fraction = (
                            max(
                                0.0,
                                min(
                                    1.0,
                                    sum(
                                        (hv.position[d] - before[d]) * direction[d]
                                        for d in range(2)
                                    )
                                    / length2,
                                ),
                            )
                            if length2
                            else 0.0
                        )
                        projection = tuple(
                            before[d] + fraction * direction[d] for d in range(2)
                        )
                        distance = hypot(
                            projection[0] - hv.position[0],
                            projection[1] - hv.position[1],
                        )
                        scale = (
                            min(
                                1.0,
                                config.invite_radius_fraction
                                * config.comm_range
                                / distance,
                            )
                            if distance
                            else 1.0
                        )
                        point = tuple(
                            hv.position[d] + scale * (projection[d] - hv.position[d])
                            for d in range(2)
                        )
                        if not in_workspace(point, config.waypoint_workspace):
                            continue
                        identity = fresh_id(solution, "rendezvous-guest")
                        free = Visit(identity, "FREE", point)
                        routes = list(solution.routes)
                        routes[host] = (
                            host_route[:hk]
                            + (replace(hv, velocity=(0.0, 0.0)),)
                            + host_route[hk + 1 :]
                        )
                        routes[guest] = guest_route[:gk] + (free,) + guest_route[gk:]
                        yield normalize(
                            routes, solution.meetings + (Meeting(hv.id, identity),)
                        )
            # A new paired task visit is reserved for the bottleneck pair and
            # earns reward only when that task is not already in any route.
            if bottleneck is None or tuple(sorted((m, n))) != tuple(
                sorted(bottleneck[:2])
            ):
                continue
            pa = ev.trajectories[m].state(target).position if ev else problem.start
            pb = ev.trajectories[n].state(target).position if ev else problem.end
            midpoint = tuple((x + y) / 2 for x, y in zip(pa, pb))
            reached = {
                v.task_id for r in solution.routes for v in r if v.kind == "TASK"
            }
            available = sorted(
                (task for task in problem.tasks if task.id not in reached),
                key=lambda task: (
                    hypot(
                        task.position[0] - midpoint[0], task.position[1] - midpoint[1]
                    ),
                    task.id,
                ),
            )
            for task in available[:1]:
                point, task_id = task.position, task.id
                if point == problem.end:
                    continue
                for k in slots(m):
                    for j in slots(n):
                        left = fresh_id(solution, "rendezvous-left")
                        right = fresh_id(solution, "rendezvous-right")
                        a = Visit(left, "TASK", point, (0.0, 0.0), task_id)
                        b = Visit(right, "TASK", point, (0.0, 0.0), task_id)
                        routes = list(solution.routes)
                        routes[m] = route[:k] + (a,) + route[k:]
                        routes[n] = other[:j] + (b,) + other[j:]
                        yield normalize(
                            routes, solution.meetings + (Meeting(left, right),)
                        )
