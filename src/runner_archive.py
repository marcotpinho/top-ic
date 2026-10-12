"""Runner archive responsibilities."""

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


class RunnerArchiveMixin:
    def record_connectivity_change(self, result, family):
        parent = self.current_parent
        if not parent or not parent.evaluation or not parent.evaluation.communication:
            return
        old = parent.evaluation.communication
        new = result.evaluation.communication
        if new is None:
            return
        row = self.connectivity_diagnostics[family]
        row["compared"] += 1
        if (
            abs(old.peak_staleness - new.peak_staleness)
            <= self.config.schedule_tolerance
        ):
            if (
                new.integrated_excess
                < old.integrated_excess - self.config.schedule_tolerance
            ):
                row["same_peak_less_excess"] += 1
            old_peaks = sorted(
                (
                    x
                    for i, r in enumerate(old.pair_peaks)
                    for j, x in enumerate(r)
                    if i != j
                ),
                reverse=True,
            )
            new_peaks = sorted(
                (
                    x
                    for i, r in enumerate(new.pair_peaks)
                    for j, x in enumerate(r)
                    if i != j
                ),
                reverse=True,
            )
            if tuple(new_peaks) < tuple(old_peaks):
                row["same_peak_better_pair_profile"] += 1
        if old.bottleneck:
            source, receiver, t, _ = old.bottleneck

            def gap(solution):
                trajectories = solution.evaluation.trajectories
                horizon = max(x.completion_time for x in trajectories)
                p = trajectories[source].state(min(t, horizon)).position
                q = trajectories[receiver].state(min(t, horizon)).position
                return hypot(p[0] - q[0], p[1] - q[1]) - self.config.comm_range

            if gap(result) < gap(parent) - self.config.schedule_tolerance:
                row["bottleneck_pair_closer"] += 1

    def evaluate(self, candidate, family):
        self.counts["generated"] += 1
        self.operator_counts[family]["generated"] += 1
        unrefined = candidate
        if self.icc and family != "fixture":
            refined = self.refine_candidate(candidate)
            if refined is None:
                self.counts["refinement_failed"] += 1
                return None
            candidate = refined
        if candidate.key in self.seen:
            self.counts["duplicates"] += 1
            return None
        if self.exhausted():
            return None
        self.seen.add(candidate.key)
        # Safe axiswise speed lower bound includes stopped waits.
        for m, route in enumerate(candidate.routes):
            bound = sum(v.wait for v in route[:-1]) + sum(
                max(
                    abs(a.position[d] - b.position[d])
                    / self.problem.limits[m].velocity[d]
                    for d in range(2)
                )
                for a, b in zip(route, route[1:])
            )
            if bound > self.problem.time_budgets[m] + self.config.schedule_tolerance:
                self.counts["screened"] += 1
                return None
        t = perf_counter()
        result = self.evaluator.evaluate(candidate)
        self.counts["evaluation_seconds"] += perf_counter() - t
        self.counts["evaluated"] += 1
        self.operator_counts[family]["evaluated"] += 1
        if not result.evaluation.valid:
            self.counts["invalid"] += 1
            if result.evaluation.validation_status == "unresolved":
                self.counts["unresolved"] += 1
            return None
        if (
            self.icc
            and family in ("meeting", "excursion")
            and self.operator_counts[family]["generated"] % 16 == 0
            and unrefined.key != candidate.key
            and not self.exhausted()
        ):
            # A bounded paired probe also lets a useful contact survive when
            # route-time DP would erase it. Both alternatives use exact scoring.
            t = perf_counter()
            raw = self.evaluator.evaluate(unrefined)
            self.counts["refinement_probe_seconds"] += perf_counter() - t
            self.counts["refinement_probes"] += 1
            row = self.refinement_comparison[family]
            if raw.evaluation.valid:
                row["valid_pairs"] += 1
                before, after = (
                    raw.evaluation.peak_staleness,
                    result.evaluation.peak_staleness,
                )
                if after > before + self.config.schedule_tolerance:
                    row["dp_raised_delta"] += 1
                elif after < before - self.config.schedule_tolerance:
                    row["dp_lowered_delta"] += 1
                else:
                    row["dp_same_delta"] += 1
                raw_rank = (
                    raw.objectives[2] > 0,
                    raw.objectives[1] if raw.objectives[2] == 0 else raw.objectives[2],
                    raw.objectives[1],
                )
                dp_rank = (
                    result.objectives[2] > 0,
                    result.objectives[1]
                    if result.objectives[2] == 0
                    else result.objectives[2],
                    result.objectives[1],
                )
                if raw_rank < dp_rank and raw.key not in self.seen:
                    result = raw
                    self.seen.add(raw.key)
                    row["raw_chosen"] += 1
            else:
                row["raw_invalid"] += 1
        if self.icc:
            self.record_connectivity_change(result, family)
        if self.icc:
            self._remember(result)
        self.counts["valid"] += 1
        self.operator_counts[family]["valid"] += 1
        if self.archive.add(result):
            self.counts["accepted"] += 1
            self.operator_counts[family]["accepted"] += 1
            self.log.append(
                {
                    "evaluations": self.counts["evaluated"],
                    "front": len(self.archive.front),
                    "reward": max(s.evaluation.reward for s in self.archive.front),
                }
            )
            if self.icc:
                self.archive_history.append(
                    {
                        "evaluation": self.counts["evaluated"],
                        "iteration": self.iterations,
                        "family": family,
                        "front": [s.objectives for s in self.archive.front],
                    }
                )
        elif self.icc:
            self.dominated.add(result, self.archive.front)
        if self.icc:
            self.dominated.solutions = [
                s
                for s in self.dominated.solutions
                if s.key not in {f.key for f in self.archive.front}
            ]
        return result

    def refine_candidate(self, candidate):
        """Canonicalize ICC visit states before scoring a structural candidate."""
        forced = {
            identity
            for pair in candidate.meetings
            for identity in (pair.left, pair.right)
        }
        routes = []
        for m, route in enumerate(candidate.routes):
            key = (
                m,
                tuple(
                    (
                        v.position,
                        v.wait > 0,
                        v.id in forced,
                        v.velocity if k in (0, len(route) - 1) else None,
                    )
                    for k, v in enumerate(route)
                ),
            )
            velocities = self.velocity_cache.get(key)
            if velocities is None:
                refined = refine_route_velocities(
                    route, self.problem.limits[m], self.config, forced
                )
                if refined is None:
                    return None
                velocities = tuple(v.velocity for v in refined)
                self.velocity_cache[key] = velocities
                if len(self.velocity_cache) > 4096:
                    self.velocity_cache.pop(next(iter(self.velocity_cache)))
            routes.append(
                tuple(
                    replace(v, velocity=velocity)
                    for v, velocity in zip(route, velocities)
                )
            )
        return normalize(routes, candidate.meetings)

    def _remember(self, solution):
        self.bank_seen += 1
        cap = self.config.candidate_bank_size
        if len(self.bank) < cap:
            self.bank.append(solution)
        elif cap:
            index = self.rng.randrange(self.bank_seen)
            if index < cap:
                self.bank[index] = solution
