"""Runner seeds responsibilities."""

"""Budgeted MOVNS/VND plus a matched KOP-inspired LNS baseline."""
from dataclasses import dataclass, replace
from collections import defaultdict
from itertools import combinations, islice
from time import perf_counter
from math import hypot
import random
from .archive import Archive
from .dominated_archive import DominatedArchive, repair_coordinates
from .evaluator import Evaluator
from .solution import direct_solution
from .operators import normalize
from .neighborhoods import (
    generate,
    SINGLE_NEIGHBORHOODS,
    TEAM_NEIGHBORHOODS,
    ICC_NEIGHBORHOODS,
)
from .perturbation import RUIN_MODES, ruin, recreate
from .velocity_dp import refine_route_velocities
from .runner_models import RunResult


class RunnerSeedsMixin:
    def cooperative_seed(self, direct, limit, deadline=None):
        current = direct
        if "insert" not in self.families:
            return current
        while (
            not self.exhausted()
            and self.counts["evaluated"] < limit
            and (deadline is None or perf_counter() < deadline)
        ):
            best = None
            rank = None
            reached = set().union(*current.evaluation.reached_tasks)
            for task in self.problem.tasks:
                if task.id in reached:
                    continue
                from .solution import Visit

                routes = []
                for m, r in enumerate(current.routes):
                    v = Visit(
                        f"cooperative:{m}:{task.id}",
                        "TASK",
                        task.position,
                        (0.0, 0.0),
                        task.id,
                    )
                    routes.append(r[:-1] + (v,) + (r[-1],))
                result = self.evaluate(normalize(routes), "cooperative_initialization")
                if result and result.evaluation.valid:
                    gain = result.evaluation.reward - current.evaluation.reward
                    cost = result.objectives[1] - current.objectives[1]
                    score = (
                        gain / max(cost, self.config.geometry_tolerance),
                        gain,
                        -result.objectives[1],
                    )
                    if gain > 0 and (rank is None or score > rank):
                        best = result
                        rank = score
                if (
                    self.exhausted()
                    or self.counts["evaluated"] >= limit
                    or deadline is not None
                    and perf_counter() >= deadline
                ):
                    break
            if best is None:
                break
            current = best
        return current

    def construct(self, base, randomized=False, evaluation_limit=None, deadline=None):
        current = base
        while not self.exhausted() and "insert" in self.families:
            if deadline is not None and perf_counter() >= deadline:
                break
            if (
                evaluation_limit is not None
                and self.counts["evaluated"] >= evaluation_limit
            ):
                break
            best = None
            rank = None
            for candidate in generate(
                "insert", current, self.problem, self.config, self.rng
            ):
                if self.exhausted():
                    break
                if deadline is not None and perf_counter() >= deadline:
                    break
                if (
                    evaluation_limit is not None
                    and self.counts["evaluated"] >= evaluation_limit
                ):
                    break
                result = self.evaluate(candidate, "construction")
                if result is None:
                    continue
                gain = result.evaluation.reward - current.evaluation.reward
                dt = result.objectives[1] - current.objectives[1]
                score = (
                    float("inf")
                    if dt <= self.config.geometry_tolerance and gain > 0
                    else gain / max(dt, self.config.geometry_tolerance),
                    gain,
                    -result.objectives[1],
                )
                if randomized:
                    score = (score[0] * self.rng.uniform(0.7, 1.3), *score[1:])
                if gain > 0 and (rank is None or score > rank):
                    best = result
                    rank = score
            if best is None:
                break
            current = best
        return current

    def assignment_seeds(self, direct, deadline):
        """Interleave spatial and random unique-task assignments across agents."""
        if not self.icc or self.problem.num_agents < 2 or "insert" not in self.families:
            return
        from .solution import Visit

        tasks = list(self.problem.tasks)
        if not tasks:
            return
        limit = self.counts["evaluated"] + min(
            6 * len(tasks), max(1, self.config.max_evaluations // 10)
        )
        patterns = []
        for axis in range(2):
            order = sorted(tasks, key=lambda t: (t.position[axis], t.id))
            # Spatial partitions let agents occupy distinct regions.
            agents = [
                min(
                    self.problem.num_agents - 1,
                    i * self.problem.num_agents // len(order),
                )
                for i in range(len(order))
            ]
            patterns.append((order, agents))
        for _ in range(4):
            order = tasks[:]
            self.rng.shuffle(order)
            agents = [i % self.problem.num_agents for i in range(len(order))]
            self.rng.shuffle(agents)
            patterns.append((order, agents))
        currents = [direct for _ in patterns]
        # Round-robin prevents the first pattern from spending all seed time.
        for index in range(len(tasks)):
            for pattern, (order, agents) in enumerate(patterns):
                if (
                    self.exhausted()
                    or perf_counter() >= deadline
                    or self.counts["evaluated"] >= limit
                ):
                    return
                task = order[index]
                agent = agents[index]
                current = currents[pattern]
                visit = Visit(
                    f"assignment-seed:{pattern}:{agent}:{task.id}",
                    "TASK",
                    task.position,
                    (0.0, 0.0),
                    task.id,
                )
                candidate = normalize(
                    tuple(
                        r if m != agent else r[:-1] + (visit, r[-1])
                        for m, r in enumerate(current.routes)
                    )
                )
                assessed = self.evaluate(candidate, "assignment_seed")
                if assessed is not None:
                    currents[pattern] = assessed
