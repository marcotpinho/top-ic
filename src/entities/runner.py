"""TOP-CC-shaped orchestration of the rebuilt seeded MOVNS search."""

from collections import Counter
from random import Random
from statistics import median
from time import perf_counter

from ..config import Config, Problem
from ..runner_models import RunResult
from ..solution import Solution, direct_solution
from .archive import Archive
from .archive_updates import evaluate_candidate
from .evaluator import Evaluator
from .hypervolume import hypervolume_2d
from .neighborhood import Neighborhood
from .profiling import SearchProfile
from .search_loop import run_iterations
from .seed_construction import (
    construct_reward_seed,
    cooperative_seeds,
    partition_seeds,
)
from .statistics import finish


class Runner:
    """Own one RNG and pass it through all stochastic search components."""

    def __init__(self, problem: Problem, config: Config) -> None:
        if config.mode != "team_kop_icc":
            raise ValueError("The rebuilt Runner supports team_kop_icc only")
        self.problem = problem
        self.config = config
        self.rng = Random(config.seed)
        self.evaluator = Evaluator(problem, config)
        self.archive = Archive(problem, config, self.rng)
        self.neighborhood = Neighborhood(problem, config, self.rng)
        self.profile = SearchProfile.for_neighborhoods(self.neighborhood.names)
        self.counts: Counter[str] = Counter()
        self.by_family: dict[str, Counter[str]] = {}
        self.seen: set[object] = set()
        self.history: list[dict] = []
        self.objective_history: list[dict] = []
        self.budget_repairs: list[dict] = []
        self.active_base: Solution | None = None
        self.active_base_source: str | None = None
        self.repair_history: list[dict] = []
        self.metrics_history: list[dict] = []
        self.initialization_history: list[dict] = []
        self.started = 0.0
        self.iterations = 0

    def exhausted(self) -> bool:
        """Stop after the evaluation or elapsed-time allowance."""
        return (
            self.counts["exact_evaluations"] >= self.config.max_evaluations
            or perf_counter() - self.started >= self.config.max_seconds
        )

    def initialization_exhausted(self) -> bool:
        """Reserve most wall time and exact evaluations for repair and VND."""
        fraction = self.config.initialization_budget_fraction
        return self.exhausted() or (
            self.counts["exact_evaluations"] >= self.config.max_evaluations * fraction
            or perf_counter() - self.started >= self.config.max_seconds * fraction
        )

    def evaluate(self, solution: Solution, family: str) -> Solution | None:
        """Evaluate one complete decision and update archive/pool (eqs. 1–16)."""
        started = perf_counter()
        try:
            return evaluate_candidate(self, solution, family)
        finally:
            self.profile.evaluation_seconds += perf_counter() - started

    def run(self) -> RunResult:
        """Construct seeds, then run independent sampled family searches."""
        self.started = perf_counter()
        direct = self.evaluate(direct_solution(self.problem), "initialization")
        if direct is None:
            return finish(self, "no_known_feasible_seed")
        construct_reward_seed(self, direct)
        for cooperative in cooperative_seeds(direct, self.problem):
            if self.initialization_exhausted():
                break
            self.evaluate(cooperative, "cooperative_seed")
        for seed in partition_seeds(direct, self.problem, self.rng):
            if self.initialization_exhausted():
                break
            self.evaluate(seed, "partition_seed")
        self.record_archive_objectives(0)
        self.record_metrics(0)
        run_iterations(self)
        status = "ok" if self.archive.front else "no_physically_feasible_solution"
        return finish(self, status)

    def record_archive_objectives(self, iteration: int) -> None:
        """Save every current archive objective vector at an iteration boundary."""
        scales = self.hypervolume_scales()
        objective_vectors = []
        for solution in self.archive.front:
            objectives = solution.objectives
            if objectives is not None:
                objective_vectors.append(objectives)
        self.objective_history.append(
            {
                "iteration": iteration,
                "objectives": [list(objectives) for objectives in objective_vectors],
                "hypervolume": hypervolume_2d(
                    self._normalize_objectives(objectives, scales)
                    for objectives in objective_vectors
                ),
            }
        )

    def record_metrics(self, iteration: int) -> None:
        """Record health, coverage, CV, cache, and quality against exact evaluations."""
        pool_cvs = [item.evaluation.comm_violation for item in self.archive.pool]
        front_regions = {
            self.archive.coverage.subregion(item) for item in self.archive.front
        }
        pool_regions = {
            self.archive.coverage.subregion(item) for item in self.archive.pool
        }
        requests = self.counts["cache_hits"] + self.counts["exact_evaluations"]
        selections = self.archive.selection_history
        pool_selections = sum(row["source"] == "pool" for row in selections)
        diagnostics = self.archive.coverage.diagnostics()
        last_selection = selections[-1] if selections else {}
        self.metrics_history.append(
            {
                "iteration": iteration,
                "exact_evaluations": self.counts["exact_evaluations"],
                "front_size": len(self.archive.front),
                "pool_size": len(self.archive.pool),
                "front_occupied_subregions": len(front_regions),
                "pool_occupied_subregions": len(pool_regions),
                "pool_min_cv": min(pool_cvs, default=None),
                "pool_median_cv": median(pool_cvs) if pool_cvs else None,
                "pool_mean_age": (
                    sum(diagnostics["ages"]) / len(diagnostics["ages"])
                    if diagnostics["ages"]
                    else 0.0
                ),
                "pool_age_discards": diagnostics["age_discards"],
                "pool_capacity_discards": diagnostics["capacity_discards"],
                "pool_base_fraction": pool_selections / len(selections)
                if selections
                else 0.0,
                "rho_front": last_selection.get("rho_front"),
                "rho_pool": last_selection.get("rho_pool"),
                "nd_front_size": last_selection.get("nd_front_size"),
                "nd_pool_size": last_selection.get("nd_pool_size"),
                "cache_hit_rate": self.counts["cache_hits"] / requests
                if requests
                else 0.0,
                "hypervolume": self.archive_hypervolume(),
                "maximum_reward": max(
                    (item.evaluation.reward for item in self.archive.front),
                    default=0.0,
                ),
            }
        )

    def archive_hypervolume(self) -> float:
        """Return normalized feasible-front hypervolume against reference (1, 1)."""
        scales = self.hypervolume_scales()
        objective_vectors = []
        for solution in self.archive.front:
            objectives = solution.objectives
            if objectives is not None:
                objective_vectors.append(objectives)
        return hypervolume_2d(
            self._normalize_objectives(objectives, scales)
            for objectives in objective_vectors
        )

    def hypervolume_scales(self) -> tuple[float, float]:
        """Return fixed reward and time scales for normalized hypervolume."""
        reward_scale = sum(task.reward for task in self.problem.tasks) or 1.0
        time_scale = max(self.problem.time_budgets)
        return reward_scale, time_scale

    def _normalize_objectives(
        self,
        objectives: tuple[float, ...],
        scales: tuple[float, float],
    ) -> tuple[float, float]:
        """Scale negative reward and completion time into the unit square."""
        reward_scale, time_scale = scales
        return (
            (objectives[0] + reward_scale) / reward_scale,
            objectives[1] / time_scale,
        )
