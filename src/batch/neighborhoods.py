"""Tensor-backed neighborhood proposal generation."""

from dataclasses import replace

import numpy as np

from ..config import velocity_menu
from ..entities.neighborhoods.common import changed_connectors_feasible
from ..entities.neighborhoods.relay import DIRECTIONS
from .tensors import RouteBatch, routes_to_tensor, tensor_to_solutions

SUPPORTED = {
    "remove",
    "unlink",
    "replace",
    "insert",
    "reorder",
    "assignment",
    "relay",
    "velocity_change",
    "velocity_segment",
    "velocity_agent",
    "free_near_visit",
}


def _sample(proposals, cap, rng):
    if not proposals:
        return []
    count = min(len(proposals), cap)
    return [proposals[index] for index in rng.permutation(len(proposals))[:count]]


def _workspace(points, workspace):
    if workspace is None:
        return np.ones(len(points), dtype=bool)
    xmin, xmax, ymin, ymax = workspace
    return (
        (points[:, 0] >= xmin)
        & (points[:, 0] <= xmax)
        & (points[:, 1] >= ymin)
        & (points[:, 1] <= ymax)
    )


def _candidate_batch(solution, problem, count, insertion=False):
    base = routes_to_tensor([solution], problem)
    visits = base.kind.shape[2] + int(insertion)
    shape = (count, base.kind.shape[1], visits)
    kind = np.zeros(shape, dtype=np.int8)
    task = np.full(shape, -1, dtype=np.int16)
    pos = np.zeros((*shape, 2), dtype=np.float64)
    vel = np.zeros((*shape, 2), dtype=np.float64)
    source_visits = base.kind.shape[2]
    kind[:, :, :source_visits] = base.kind[0]
    task[:, :, :source_visits] = base.task[0]
    pos[:, :, :source_visits] = base.pos[0]
    vel[:, :, :source_visits] = base.vel[0]
    nvis = np.repeat(base.nvis, count, axis=0)
    return RouteBatch(kind, task, pos, vel, nvis, base.task_ids)


def _set_row(batch, row, agent, values):
    length = len(values)
    source_kind = batch.kind[row, agent].copy()
    source_task = batch.task[row, agent].copy()
    source_pos = batch.pos[row, agent].copy()
    source_vel = batch.vel[row, agent].copy()
    batch.kind[row, agent] = 0
    batch.task[row, agent] = -1
    batch.pos[row, agent] = 0
    batch.vel[row, agent] = 0
    if length:
        indices = np.asarray(values, dtype=np.int64)
        batch.kind[row, agent, :length] = source_kind[indices]
        batch.task[row, agent, :length] = source_task[indices]
        batch.pos[row, agent, :length] = source_pos[indices]
        batch.vel[row, agent, :length] = source_vel[indices]
    batch.nvis[row, agent] = length


def _insert(batch, row, agent, index, kind, task, position, velocity):
    length = int(batch.nvis[row, agent])
    batch.kind[row, agent, index + 1 : length + 1] = batch.kind[
        row, agent, index:length
    ].copy()
    batch.task[row, agent, index + 1 : length + 1] = batch.task[
        row, agent, index:length
    ].copy()
    batch.pos[row, agent, index + 1 : length + 1] = batch.pos[
        row, agent, index:length
    ].copy()
    batch.vel[row, agent, index + 1 : length + 1] = batch.vel[
        row, agent, index:length
    ].copy()
    batch.kind[row, agent, index] = kind
    batch.task[row, agent, index] = task
    batch.pos[row, agent, index] = position
    batch.vel[row, agent, index] = velocity
    batch.nvis[row, agent] += 1


def _dedupe(solutions):
    unique = {}
    for solution in solutions:
        unique.setdefault(solution.key, solution)
    return list(unique.values())


def _indexed(name, solution, problem, config, rng):
    proposals = []
    if name in {"remove", "unlink"}:
        code = 2 if name == "remove" else 3
        proposals = [
            (agent, index)
            for agent, route in enumerate(solution.routes)
            for index in range(1, len(route) - 1)
            if (route[index].kind == "TASK") == (code == 2)
            and (route[index].kind == "FREE") == (code == 3)
        ]
    elif name == "replace":
        reached = {
            visit.task_id
            for route in solution.routes
            for visit in route
            if visit.kind == "TASK"
        }
        proposals = [
            (agent, index, task_index)
            for task_index, task in enumerate(problem.tasks)
            if task.id not in reached
            for agent, route in enumerate(solution.routes)
            for index in range(1, len(route) - 1)
            if route[index].kind == "TASK"
        ]
    elif name == "insert":
        reached = {
            visit.task_id
            for route in solution.routes
            for visit in route
            if visit.kind == "TASK"
        }
        proposals = [
            (agent, index, task_index)
            for task_index, task in enumerate(problem.tasks)
            if task.id not in reached
            for agent, route in enumerate(solution.routes)
            for index in range(1, len(route))
        ]
    elif name == "reorder":
        proposals = [
            (kind, agent, left, right)
            for kind in ("relocate", "swap", "reverse")
            for agent, route in enumerate(solution.routes)
            for left in range(1, len(route) - 1)
            for right in range(left + 1, len(route) - 1)
        ]
    else:
        tasks = [
            (agent, index)
            for agent, route in enumerate(solution.routes)
            for index in range(1, len(route) - 1)
            if route[index].kind == "TASK"
        ]
        proposals.extend(
            ("transfer", agent, index, other, insertion)
            for agent, index in tasks
            for other, route in enumerate(solution.routes)
            if other != agent
            for insertion in range(1, len(route))
        )
        proposals.extend(
            ("exchange", agent, index, other, partner)
            for agent, index in tasks
            for other, partner in tasks
            if agent < other
        )
    proposals = _sample(proposals, config.neighborhood_candidates, rng)
    if not proposals:
        return []
    insertion = name in {"insert", "assignment"}
    batch = _candidate_batch(solution, problem, len(proposals), insertion)
    for row, proposal in enumerate(proposals):
        if name in {"remove", "unlink"}:
            agent, index = proposal
            order = [i for i in range(len(solution.routes[agent])) if i != index]
            _set_row(batch, row, agent, order)
        elif name == "replace":
            agent, index, task_index = proposal
            batch.task[row, agent, index] = task_index
            batch.pos[row, agent, index] = problem.tasks[task_index].position
        elif name == "insert":
            agent, index, task_index = proposal
            _insert(
                batch,
                row,
                agent,
                index,
                2,
                task_index,
                problem.tasks[task_index].position,
                batch.vel[row, agent, index - 1].copy(),
            )
        elif name == "reorder":
            kind, agent, left, right = proposal
            order = list(range(len(solution.routes[agent])))
            if kind == "relocate":
                order.insert(right, order.pop(left))
            elif kind == "swap":
                order[left], order[right] = order[right], order[left]
            else:
                order[left : right + 1] = reversed(order[left : right + 1])
            _set_row(batch, row, agent, order)
        else:
            kind, agent, index, other, partner = proposal
            if kind == "transfer":
                moved = (
                    batch.kind[row, agent, index].copy(),
                    batch.task[row, agent, index].copy(),
                    batch.pos[row, agent, index].copy(),
                )
                source_order = [
                    i for i in range(len(solution.routes[agent])) if i != index
                ]
                _set_row(batch, row, agent, source_order)
                _insert(
                    batch,
                    row,
                    other,
                    partner,
                    moved[0],
                    moved[1],
                    moved[2],
                    batch.vel[row, other, 0].copy(),
                )
            else:
                left = (
                    batch.kind[row, agent, index].copy(),
                    batch.task[row, agent, index].copy(),
                    batch.pos[row, agent, index].copy(),
                )
                right = (
                    batch.kind[row, other, partner].copy(),
                    batch.task[row, other, partner].copy(),
                    batch.pos[row, other, partner].copy(),
                )
                batch.kind[row, agent, index] = right[0]
                batch.task[row, agent, index] = right[1]
                batch.pos[row, agent, index] = right[2]
                batch.vel[row, agent, index] = batch.vel[row, agent, 0]
                batch.kind[row, other, partner] = left[0]
                batch.task[row, other, partner] = left[1]
                batch.pos[row, other, partner] = left[2]
                batch.vel[row, other, partner] = batch.vel[row, other, 0]
    return _dedupe(tensor_to_solutions(batch))


def _relay(solution, problem, config, rng):
    visitors = {}
    for agent, route in enumerate(solution.routes):
        for visit in route[1:-1]:
            if visit.kind == "TASK":
                visitors.setdefault(visit.task_id, set()).add(agent)
    shared = [
        (agent, index)
        for agent, route in enumerate(solution.routes)
        for index, visit in enumerate(route[1:-1], 1)
        if visit.kind == "TASK" and visitors[visit.task_id] - {agent}
    ]
    if not shared:
        return []
    directions = np.asarray(DIRECTIONS, dtype=np.float64)
    proposals = []
    for agent, index in shared:
        points = np.asarray(solution.routes[agent][index].position) + np.concatenate(
            [
                fraction * config.comm_range * directions
                for fraction in config.relay_radius_fractions
            ]
        )
        proposals.extend(
            (agent, index, point)
            for point, valid in zip(
                points, _workspace(points, config.waypoint_workspace)
            )
            if valid
        )
    proposals = _sample(proposals, config.neighborhood_candidates, rng)
    if not proposals:
        return []
    batch = _candidate_batch(solution, problem, len(proposals))
    for row, (agent, index, point) in enumerate(proposals):
        batch.kind[row, agent, index] = 3
        batch.task[row, agent, index] = -1
        batch.pos[row, agent, index] = point
    return _dedupe(tensor_to_solutions(batch))


def _velocity(name, solution, problem, config, rng):
    proposals = []
    if name == "velocity_change":
        for agent, route in enumerate(solution.routes):
            for index, visit in enumerate(route[1:-1], 1):
                proposals.extend(
                    (agent, index, velocity)
                    for velocity in velocity_menu(problem.limits[agent], config)
                    if velocity != visit.velocity
                )
    elif name == "velocity_agent":
        proposals = [
            (agent, fraction)
            for agent, route in enumerate(solution.routes)
            if len(route) > 2
            for fraction in config.speed_fractions
        ]
    else:
        segments = [
            (agent, start, length)
            for agent, route in enumerate(solution.routes)
            for length in config.velocity_segment_lengths
            for start in range(1, len(route) - length)
        ]
        if not segments:
            return []
        proposals = [
            segments[index]
            for index in rng.integers(0, len(segments), config.neighborhood_candidates)
        ]
    proposals = (
        _sample(proposals, config.neighborhood_candidates, rng)
        if name != "velocity_segment"
        else proposals
    )
    batch = _candidate_batch(solution, problem, len(proposals))
    changed_ranges = []
    for row, proposal in enumerate(proposals):
        if name == "velocity_change":
            agent, index, velocity = proposal
            batch.vel[row, agent, index] = velocity
            changed_ranges.append((agent, index, index))
        elif name == "velocity_agent":
            agent, fraction = proposal
            menu = np.asarray(
                velocity_menu(
                    problem.limits[agent], replace(config, speed_fractions=(fraction,))
                )
            )
            for index, visit in enumerate(solution.routes[agent][1:-1], 1):
                scores = (
                    menu @ np.asarray(visit.velocity) / np.linalg.norm(menu, axis=1)
                )
                batch.vel[row, agent, index] = menu[int(np.argmax(scores))]
            changed_ranges.append((agent, 1, len(solution.routes[agent]) - 2))
        else:
            agent, start, length = proposal
            menu = np.asarray(velocity_menu(problem.limits[agent], config))
            for index in range(start, start + length):
                current = batch.vel[row, agent, index]
                choices = menu[np.any(menu != current, axis=1)]
                batch.vel[row, agent, index] = choices[rng.integers(len(choices))]
            changed_ranges.append((agent, start, start + length - 1))
    candidates = tensor_to_solutions(batch)
    feasible = [
        candidate
        for candidate, (agent, first, last) in zip(candidates, changed_ranges)
        if candidate.key[agent] != solution.key[agent]
        and changed_connectors_feasible(
            candidate.routes[agent], first, last, problem.limits[agent]
        )
    ]
    return _dedupe(feasible)


def _free_near(solution, problem, config, rng):
    proposals = [
        (anchor_agent, anchor.position, target_agent, insertion)
        for anchor_agent, anchor_route in enumerate(solution.routes)
        for anchor in anchor_route
        for target_agent, target_route in enumerate(solution.routes)
        if target_agent != anchor_agent
        for insertion in range(1, len(target_route))
    ]
    if not proposals:
        return []
    angles = rng.uniform(0.0, 2 * np.pi, len(proposals))
    radii = config.comm_range * np.sqrt(rng.random(len(proposals)))
    points = np.asarray([item[1] for item in proposals]) + np.column_stack(
        (radii * np.cos(angles), radii * np.sin(angles))
    )
    proposals = [
        (*proposal[2:], point)
        for proposal, point, valid in zip(
            proposals, points, _workspace(points, config.waypoint_workspace)
        )
        if valid
    ]
    proposals = _sample(proposals, config.neighborhood_candidates, rng)
    if not proposals:
        return []
    batch = _candidate_batch(solution, problem, len(proposals), True)
    for row, (agent, insertion, point) in enumerate(proposals):
        _insert(
            batch,
            row,
            agent,
            insertion,
            3,
            -1,
            point,
            batch.vel[row, agent, insertion - 1].copy(),
        )
    candidates = tensor_to_solutions(batch)
    return _dedupe(
        candidate
        for candidate, (agent, insertion, _) in zip(candidates, proposals)
        if changed_connectors_feasible(
            candidate.routes[agent], insertion, insertion, problem.limits[agent]
        )
    )


def generate(name, solution, problem, config, rng):
    if name in {"remove", "unlink", "replace", "insert", "reorder", "assignment"}:
        return _indexed(name, solution, problem, config, rng)
    if name == "relay":
        return _relay(solution, problem, config, rng)
    if name in {"velocity_change", "velocity_segment", "velocity_agent"}:
        return _velocity(name, solution, problem, config, rng)
    if name == "free_near_visit":
        return _free_near(solution, problem, config, rng)
    raise ValueError(f"Unsupported tensor neighborhood: {name}")
