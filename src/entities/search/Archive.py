"""Feasible epsilon archive and three-objective Pareto pool."""

from random import Random

from ..problem.Config import Config
from ...solution import Solution
from ..profiling import profiling
from ..selection import select_base
from .ParetoPool import ParetoPool
from .SearchProfile import SearchProfile
from .epsilon.Archive import Archive as EpsilonArchive


class Archive:
    """Maintain feasible Pareto representatives and every other valid candidate."""

    def __init__(
        self, config: Config, rng: Random, profile: SearchProfile | None = None
    ) -> None:
        self.profile = profile if profile is not None else SearchProfile()
        self.rng = rng
        self.pool_selection_enabled = config.pool_selection_enabled
        self.selection_policy = config.selection_policy
        self.elite_selection_probability = config.elite_selection_probability
        self.pool_selection_probability = config.pool_selection_probability
        self.elite_cooldown_after = config.elite_cooldown_after
        self.elite_cooldown_iterations = config.elite_cooldown_iterations
        self.elite_failures = 0
        self.elite_cooldown_remaining = 0
        self.tolerance = config.numerical_tolerance
        self.epsilon = EpsilonArchive(
            config.archive_size,
            config.eps_reward,
            config.eps_time,
        )
        self.pareto_pool = ParetoPool(
            config.dominated_archive_size, config.pool_max_age, self.profile
        )
        self.selection_history: list[dict] = []
        self.selection_source_stats = {
            source: {"attempts": 0, "improvements": 0, "hypervolume_gain": 0.0, "evaluations": 0}
            for source in ("elite", "front", "pool")
        }
        self.last_addition = {"front": False, "pool": False, "displaced": 0}

    @property
    def front(self) -> list[Solution]:
        return self.epsilon.front

    @property
    def pool(self) -> list[Solution]:
        return self.pareto_pool.solutions

    def _communication_feasible(self, solution: Solution) -> bool:
        return solution.evaluation.comm_violation <= self.tolerance

    def add(self, solution: Solution) -> bool:
        """Route every physically valid solution through F and then P."""
        self.last_addition = {"front": False, "pool": False, "displaced": 0}
        if not solution.evaluation or not solution.evaluation.valid:
            return False
        with profiling(self.profile, "front_update_seconds"):
            previous_front = list(self.front)
            retained = False
            displaced = []
            if self._communication_feasible(solution) and not any(
                incumbent.dominates(solution) for incumbent in previous_front
            ):
                survivors = [
                    incumbent
                    for incumbent in previous_front
                    if not solution.dominates(incumbent)
                ]
                self.epsilon.front = survivors
                self.epsilon.alternatives = []
                retained = self.epsilon.add(solution)
                front_keys = {item.key for item in self.front}
                displaced = [
                    item for item in previous_front if item.key not in front_keys
                ]
        with profiling(self.profile, "pool_update_seconds"):
            pool_candidates = list(displaced)
            if not retained:
                pool_candidates.append(solution)
            before_pool = {item.key for item in self.pool}
            self.pareto_pool.update(pool_candidates, self.front)
            after_pool = {item.key for item in self.pool}
            self.last_addition = {
                "front": retained,
                "pool": solution.key in after_pool and solution.key not in before_pool,
                "displaced": len(displaced),
            }
        return retained

    def select(self, iteration: int) -> Solution:
        elite_enabled = self.elite_cooldown_remaining == 0
        if self.elite_cooldown_remaining:
            self.elite_cooldown_remaining -= 1
        probabilities = self._adaptive_probabilities(elite_enabled)
        with profiling(self.profile, "base_selection_seconds"):
            solution, record = select_base(
                self.front,
                self.pool,
                self.rng,
                self.selection_policy,
                self.pool_selection_enabled,
                probabilities["elite"],
                probabilities["pool"],
                elite_enabled,
            )
        with profiling(self.profile, "recording_seconds"):
            record["iteration"] = iteration + 1
            self.selection_history.append(record)
        return solution

    def _adaptive_probabilities(self, elite_enabled: bool) -> dict[str, float]:
        configured = {
            "elite": self.elite_selection_probability if elite_enabled and self.front else 0.0,
            "pool": self.pool_selection_probability if self.pool_selection_enabled and self.pool else 0.0,
        }
        configured["front"] = max(0.0, 1.0 - configured["elite"] - configured["pool"])
        weights = {}
        for source, base in configured.items():
            stats = self.selection_source_stats[source]
            success = (stats["improvements"] + 1) / (stats["attempts"] + 2)
            weights[source] = base * (0.25 + success)
        total = sum(weights.values())
        return {
            source: weight / total if total else configured[source]
            for source, weight in weights.items()
        }

    def mark_expansion(self, solution: Solution, improved: bool) -> None:
        with profiling(self.profile, "pool_maintenance_seconds"):
            self.pareto_pool.set_expansion_result(solution, improved)
            if self.selection_history:
                record = self.selection_history[-1]
                record["improved"] = improved
                source = record["source"]
                stats = self.selection_source_stats[source]
                stats["attempts"] += 1
                stats["improvements"] += int(improved)
                stats["hypervolume_gain"] += record.get("hypervolume_gain", 0.0)
                stats["evaluations"] += record.get("exact_evaluations_spent", 0)
                record["source_stats"] = dict(stats)
                if source == "elite":
                    self.elite_failures = 0 if improved else self.elite_failures + 1
                    if self.elite_failures >= self.elite_cooldown_after:
                        self.elite_failures = 0
                        self.elite_cooldown_remaining = self.elite_cooldown_iterations
                record["elite_failures"] = self.elite_failures
                record["elite_cooldown_remaining"] = (
                    self.elite_cooldown_remaining
                )
