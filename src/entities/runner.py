"""TOP-CC-shaped orchestration of the rebuilt seeded MOVNS search."""

from collections import Counter
from random import Random
from time import perf_counter

from ..config import Config, Problem
from ..runner_models import RunResult
from ..solution import Solution, direct_solution
from .archive import Archive
from .archive_updates import evaluate_candidate
from .evaluator import Evaluator
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
        self.archive = Archive(config, self.rng)
        self.neighborhood = Neighborhood(problem, config, self.rng)
        self.profile = SearchProfile.for_neighborhoods(self.neighborhood.names)
        self.counts: Counter[str] = Counter()
        self.by_family: dict[str, Counter[str]] = {}
        self.seen: set[object] = set()
        self.history: list[dict] = []
        self.objective_history: list[dict] = []
        self.started = 0.0
        self.iterations = 0

    def exhausted(self) -> bool:
        """Stop after the evaluation or elapsed-time allowance."""
        return (
            self.counts["evaluated"] >= self.config.max_evaluations
            or perf_counter() - self.started >= self.config.max_seconds
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
            if self.exhausted():
                break
            self.evaluate(cooperative, "cooperative_seed")
        for seed in partition_seeds(direct, self.problem, self.rng):
            if self.exhausted():
                break
            self.evaluate(seed, "partition_seed")
        self.record_archive_objectives(0)
        run_iterations(self)
        status = "ok" if self.archive.front else "no_physically_feasible_solution"
        return finish(self, status)

    def record_archive_objectives(self, iteration: int) -> None:
        """Save every current archive objective vector at an iteration boundary."""
        self.objective_history.append(
            {
                "iteration": iteration,
                "objectives": [
                    list(solution.objectives) for solution in self.archive.front
                ],
            }
        )
