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
from .parallel_evaluation import ParallelEvaluation
from .profiling import SearchProfile, profiling
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
        self.problem = problem
        self.config = config
        self.rng = Random(config.seed)
        self.evaluator = Evaluator(problem, config)
        self.neighborhood = Neighborhood(problem, config, self.rng)
        self.profile = SearchProfile.for_neighborhoods(self.neighborhood.names)
        self.archive = Archive(config, self.rng, self.profile)
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
        self.reserved_evaluations = 0
        self.parallel_evaluation = ParallelEvaluation(self)

    def exhausted(self) -> bool:
        """Stop after the evaluation or elapsed-time allowance."""
        return (
            self.counts["exact_evaluations"] + self.reserved_evaluations
            >= self.config.max_evaluations
            or perf_counter() - self.started >= self.config.max_seconds
        )

    def initialization_exhausted(self) -> bool:
        """Reserve most wall time and exact evaluations for repair and VND."""
        fraction = self.config.initialization_budget_fraction
        return self.exhausted() or (
            self.counts["exact_evaluations"] >= self.config.max_evaluations * fraction
            or perf_counter() - self.started >= self.config.max_seconds * fraction
        )

    def evaluate(
        self, solution: Solution, family: str, parent: Solution | None = None
    ) -> Solution | None:
        """Evaluate one complete decision and update archive/pool (eqs. 1–16)."""
        with profiling(self.profile, "evaluation_seconds"):
            return evaluate_candidate(self, solution, family, parent)

    def evaluate_batch(self, candidates, family: str, parent: Solution):
        with profiling(self.profile, "evaluation_seconds"):
            return self.parallel_evaluation.evaluate_batch(candidates, family, parent)

    def run(self) -> RunResult:
        try:
            status = self._run_search()
        finally:
            self.parallel_evaluation.close()
        return finish(self, status)

    def _run_search(self) -> str:
        """Construct seeds, then run independent sampled family searches."""
        self.started = perf_counter()
        direct = self.evaluate(direct_solution(self.problem), "initialization")
        if direct is None:
            return "no_known_feasible_seed"
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
        return status

    def record_archive_objectives(self, iteration: int) -> None:
        """Save every current archive objective vector at an iteration boundary."""
        with profiling(self.profile, "recording_seconds"):
            scales = self.hypervolume_scales()
            objective_vectors = []
            for solution in self.archive.front:
                objectives = solution.objectives
                if objectives is not None:
                    objective_vectors.append(objectives)
            self.objective_history.append(
                {
                    "iteration": iteration,
                    "objectives": [
                        list(objectives) for objectives in objective_vectors
                    ],
                    "hypervolume": hypervolume_2d(
                        self._normalize_objectives(objectives, scales)
                        for objectives in objective_vectors
                    ),
                }
            )

    def record_metrics(self, iteration: int) -> None:
        """Record archive health, CV, cache, and quality against exact evaluations."""
        with profiling(self.profile, "recording_seconds"):
            pool_cvs = [item.evaluation.comm_violation for item in self.archive.pool]
            requests = self.counts["cache_hits"] + self.counts["exact_evaluations"]
            selections = self.archive.selection_history
            pool_selections = sum(row["source"] == "pool" for row in selections)
            diagnostics = self.archive.pareto_pool.diagnostics()
            last_selection = selections[-1] if selections else {}
            self.metrics_history.append(
                {
                    "iteration": iteration,
                    "exact_evaluations": self.counts["exact_evaluations"],
                    "front_size": len(self.archive.front),
                    "pool_size": len(self.archive.pool),
                    "pool_min_cv": min(pool_cvs, default=None),
                    "pool_median_cv": median(pool_cvs) if pool_cvs else None,
                    "pool_mean_age": (
                        sum(diagnostics["ages"]) / len(diagnostics["ages"])
                        if diagnostics["ages"]
                        else 0.0
                    ),
                    "pool_age_discards": diagnostics["age_discards"],
                    "pool_capacity_discards": diagnostics["capacity_discards"],
                    "pool_dominance_discards": diagnostics["dominance_discards"],
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
