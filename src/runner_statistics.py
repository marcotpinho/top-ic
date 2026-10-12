"""Runner statistics responsibilities."""

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


class RunnerStatisticsMixin:
    def record_objectives(self, phase):
        """Save independent archive extrema and the highest-reward representative."""
        front = self.archive.front
        best = (
            max(front, key=lambda s: (s.evaluation.reward, -s.objectives[1]))
            if front
            else None
        )
        bounded = [s for s in front if not self.icc or s.objectives[2] == 0]
        tc_best = (
            max(bounded, key=lambda s: (s.evaluation.reward, -s.objectives[1]))
            if bounded
            else None
        )
        self.objective_history.append(
            {
                "phase": phase,
                "iteration": self.iterations,
                "evaluations": self.counts["evaluated"],
                "elapsed_seconds": perf_counter() - self.started,
                "front_size": len(front),
                "best_reward": best.evaluation.reward if best else None,
                "mean_time_at_best_reward": best.objectives[1] if best else None,
                "minimum_mean_time": min(s.objectives[1] for s in front)
                if front
                else None,
                "minimum_violation": min(s.objectives[2] for s in front)
                if self.icc and front
                else None,
                "best_reward_at_tc": tc_best.evaluation.reward if tc_best else None,
                "mean_time_at_best_reward_at_tc": tc_best.objectives[1]
                if tc_best
                else None,
            }
        )

    def exhausted(self):
        return (
            self.counts["evaluated"] >= self.config.max_evaluations
            or perf_counter() - self.started >= self.config.max_seconds
        )

    def finish(self, status):
        from .trajectory import connect
        from .contacts import pair_contacts

        bank = {
            s.key: s
            for s in self.bank + list(self.archive.front) + self.dominated.solutions
        }
        return RunResult(
            self.problem,
            self.config,
            list(self.archive.front),
            {
                **dict(self.counts),
                "iterations": self.iterations,
                "operators": {k: dict(v) for k, v in self.operator_counts.items()},
                "log": self.log,
                "objective_history": self.objective_history,
                "archive_history": self.archive_history if self.icc else [],
                "seed_selection_history": self.seed_selection_history,
                "refinement_comparison": {
                    family: dict(row)
                    for family, row in self.refinement_comparison.items()
                },
                "connectivity_diagnostics": {
                    family: dict(row)
                    for family, row in self.connectivity_diagnostics.items()
                },
                "archive_policy": "epsilon_box_dominance",
                "effective_epsilon": self.archive.epsilon,
                "epsilon_coarsenings": self.archive.coarsenings,
                "connector_cache": connect.cache_info()._asdict(),
                "contact_cache": pair_contacts.cache_info()._asdict(),
                "dominated_archive_size": len(self.dominated.solutions),
                "candidate_bank_size": len(bank) if self.icc else 0,
            },
            perf_counter() - self.started,
            status,
            tuple(bank.values()) if self.icc else (),
            tuple(self.dominated.solutions),
        )
