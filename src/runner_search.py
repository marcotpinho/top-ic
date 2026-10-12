"""Runner search responsibilities."""

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


class RunnerSearchMixin:
    def run(self):
        self.started = perf_counter()
        direct = self.evaluate(
            normalize(direct_solution(self.problem).routes), "initialization"
        )
        self.record_objectives("initialization")
        if direct is None:
            return self.finish("no_known_feasible_seed")
        if self.icc:
            self.cooperative_seed(
                direct,
                max(2, self.config.max_evaluations // 10),
                deadline=self.started + self.config.max_seconds * 0.06,
            )
            self.assignment_seeds(direct, self.started + self.config.max_seconds * 0.18)
        self.construct(
            direct,
            evaluation_limit=max(2, self.config.max_evaluations // 5),
            deadline=self.started + self.config.max_seconds * 0.2,
        )
        self.record_objectives("construction")
        intensity = 1
        for iteration in range(self.config.max_iterations):
            if self.exhausted() or (
                not self.archive.front and not self.dominated.solutions
            ):
                break
            self.iterations = iteration + 1
            base = self.select_seed(iteration)
            if self.config.algorithm == "lns":
                route = list(base.routes[0])
                number = max(
                    1,
                    int(
                        (len(route) - 2)
                        * (0.5 if iteration < self.config.max_iterations // 2 else 0.2)
                    ),
                )
                if "remove" in self.families:
                    for k in sorted(
                        self.rng.sample(
                            range(1, len(route) - 1), min(number, len(route) - 2)
                        ),
                        reverse=True,
                    ):
                        route.pop(k)
                destroyed = self.evaluate(normalize((tuple(route),)), "lns_destroy")
                if destroyed:
                    self.construct(destroyed, randomized=True)
                self.record_objectives("iteration")
                continue
            improved = False
            for family in self.families:
                if self.exhausted():
                    break
                accepted_before = self.counts["accepted"]
                perturbed = self.shake(base, intensity)
                self.current_parent = perturbed
                for candidate in islice(
                    self.candidate_stream(perturbed, family),
                    self.config.neighborhood_candidates,
                ):
                    if self.exhausted():
                        break
                    self.evaluate(candidate, family)
                self.current_parent = None
                if self.counts["accepted"] > accepted_before:
                    improved = True
            intensity = 1 if improved else min(4, intensity + 1)
            self.record_objectives("iteration")
        return self.finish(
            "ok" if self.archive.front else "no_physically_feasible_solution"
        )
