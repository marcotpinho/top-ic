"""Bounded, seeded ruin-and-recreate perturbations for MOVNS."""
from math import ceil, hypot

from .operators import fresh_id, normalize
from .solution import Visit


RUIN_MODES = ("route_removal", "sequence_removal", "related_removal")
DUPLICATE_REWARD_FACTOR = 0.15


def ruin(solution, mode, rng, strength=1):
    """Remove a route, a contiguous sequence, or spatially related visits."""
    routes = [list(route) for route in solution.routes]
    task_visits = [(m, k, visit) for m, route in enumerate(routes)
                   for k, visit in enumerate(route[1:-1], 1) if visit.kind == "TASK"]
    if not task_visits:
        return solution, ()

    if mode == "route_removal":
        agents = sorted({m for m, _, _ in task_visits})
        agent = rng.choice(agents)
        removed = routes[agent][1:-1]
        routes[agent] = [routes[agent][0], routes[agent][-1]]
    elif mode == "sequence_removal":
        agents = sorted({m for m, _, _ in task_visits})
        agent = rng.choice(agents)
        interior = routes[agent][1:-1]
        width = min(len(interior), max(1, strength + 1))
        task_positions = [k for k, visit in enumerate(interior) if visit.kind == "TASK"]
        anchor = rng.choice(task_positions)
        start = max(0, min(anchor - rng.randrange(width), len(interior) - width))
        removed = interior[start:start + width]
        del routes[agent][start + 1:start + width + 1]
    elif mode == "related_removal":
        _, _, seed = rng.choice(task_visits)
        count = min(len(task_visits), max(2, ceil(len(task_visits) * min(.25 + .1 * (strength - 1), .55))))
        ranked = sorted(task_visits,
                        key=lambda row: (hypot(row[2].position[0] - seed.position[0],
                                               row[2].position[1] - seed.position[1]),
                                         row[0], row[1]))
        identities = {visit.id for _, _, visit in ranked[:count]}
        removed = [visit for _, _, visit in task_visits if visit.id in identities]
        routes = [[visit for visit in route if visit.id not in identities] for route in routes]
    else:
        raise ValueError(f"Unknown ruin mode: {mode}")

    tasks = tuple(dict.fromkeys(v.task_id for v in removed if v.kind == "TASK"))
    return normalize(routes, solution.meetings), tasks


def _edge_lower_bound(before, after, limits):
    return max(abs(before[d] - after[d]) / limits.velocity[d] for d in range(2))


def _axis_lower_bound(route, limits):
    return sum(_edge_lower_bound(a.position, b.position, limits)
               for a, b in zip(route, route[1:]))


def recreate(ruined, problem, rng, removed_tasks, strength=1):
    """Produce noisy insertion prefixes; the runner validates them in reverse.

    Duplicate visits retain 15% of task reward in the construction score.
    This is a search bias, not a change to the evaluator's shared reward.
    """
    current = ruined
    prefixes = []
    target = min(6, max(1, len(removed_tasks) + min(2, max(0, strength - 1)) + rng.randrange(3)))
    tasks = sorted(problem.tasks, key=lambda task: task.id)
    for _ in range(target):
        options = []
        visits_by_agent = [{v.task_id for v in route if v.kind == "TASK"}
                           for route in current.routes]
        for task in tasks:
            if task.reward <= 0:
                continue
            for agent, route in enumerate(current.routes):
                if task.id in visits_by_agent[agent]:
                    continue
                duplicated = any(task.id in visits_by_agent[other]
                                 for other in range(len(current.routes)) if other != agent)
                reward = task.reward * (DUPLICATE_REWARD_FACTOR if duplicated else 1.)
                limits = problem.limits[agent]
                baseline = _axis_lower_bound(route, limits)
                placements = []
                for index in range(1, len(route)):
                    before, after = route[index - 1].position, route[index].position
                    lower_bound = (baseline + _edge_lower_bound(before, task.position, limits) +
                                   _edge_lower_bound(task.position, after, limits) -
                                   _edge_lower_bound(before, after, limits))
                    if lower_bound > problem.time_budgets[agent] + 1e-8:
                        continue
                    detour = (hypot(task.position[0] - before[0], task.position[1] - before[1]) +
                              hypot(after[0] - task.position[0], after[1] - task.position[1]) -
                              hypot(after[0] - before[0], after[1] - before[1]))
                    speed = max(limits.velocity)
                    score = reward / (1. + max(0., detour) / speed)
                    placements.append((score, index))
                for score, index in sorted(placements, reverse=True)[:2]:
                    # Noise and stochastic choice among good placements avoid
                    # rebuilding the same deterministic route every time.
                    options.append((score * rng.uniform(.65, 1.35), agent, index, task))
        if not options:
            break
        shortlist = sorted(options, key=lambda row: (-row[0], row[1], row[2], row[3].id))[:max(8, 3 * problem.num_agents)]
        scale=max(row[0] for row in shortlist)
        selected = rng.choices(shortlist, weights=[max(row[0] / scale, 1e-12) ** 2 for row in shortlist], k=1)[0]
        _, agent, index, task = selected
        routes = list(current.routes)
        visit = Visit(fresh_id(current, "recreate-task"), "TASK", task.position, task_id=task.id)
        routes[agent] = routes[agent][:index] + (visit,) + routes[agent][index:]
        current = normalize(routes, current.meetings)
        prefixes.append(current)
    return tuple(prefixes)
