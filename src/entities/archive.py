"""Feasible epsilon archive and three-objective Pareto pool."""

from random import Random

from ..archive import Archive as EpsilonArchive
from ..config import Config
from ..solution import Solution
from .pool import ParetoPool
from .profiling import SearchProfile, profiling
from .selection import select_base


class Archive:
    """Maintain feasible Pareto representatives and every other valid candidate."""

    def __init__(
        self, config: Config, rng: Random, profile: SearchProfile | None = None
    ) -> None:
        self.profile = profile if profile is not None else SearchProfile()
        self.rng = rng
        self.pool_selection_enabled = config.pool_selection_enabled
        self.selection_policy = config.selection_policy
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
        with profiling(self.profile, "base_selection_seconds"):
            solution, record = select_base(
                self.front,
                self.pool,
                self.rng,
                self.selection_policy,
                self.pool_selection_enabled,
            )
        with profiling(self.profile, "recording_seconds"):
            record["iteration"] = iteration + 1
            self.selection_history.append(record)
        return solution

    def mark_expansion(self, solution: Solution, improved: bool) -> None:
        with profiling(self.profile, "pool_maintenance_seconds"):
            self.pareto_pool.set_expansion_result(solution, improved)
            if self.selection_history:
                self.selection_history[-1]["improved"] = improved
