"""Named neighborhood registry and the single explicit random stream."""

from collections.abc import Iterator
from importlib import import_module
from itertools import islice
from random import Random

import numpy as np

from ...core.neighborhoods.registry import ICC_NEIGHBORHOODS
from ...core.search.profiling import profiling
from ..problem.Config import Config
from ..problem.Problem import Problem
from ..routing.Solution import Solution


class Neighborhood:
    """Dispatch sampled families without changing their shared interface."""

    ICC = ICC_NEIGHBORHOODS

    def __init__(self, problem: Problem, config: Config, rng: Random) -> None:
        self.problem = problem
        self.config = config
        self.rng = rng
        self.batch_rng = np.random.default_rng(
            np.random.SeedSequence([config.seed, 0xB47C])
        )
        self.names = tuple(name for name in self.ICC if name not in config.disabled)
        self.executions: list[dict] = []

    def generate(
        self,
        name: str,
        solution: Solution,
        *,
        phase: str = "search",
        iteration: int | None = None,
        pass_index: int | None = None,
    ) -> Iterator[Solution]:
        """Run one family with the Runner RNG and configured candidate cap."""
        if name not in self.names:
            raise ValueError(f"Disabled or unknown neighborhood: {name}")
        if self.config.batch_neighborhoods:
            from ...core.neighborhoods.batch import SUPPORTED, generate

            if name in SUPPORTED:
                candidates = generate(
                    name,
                    solution,
                    self.problem,
                    self.config,
                    self.batch_rng,
                )
            else:
                module = import_module(f"topcc.core.neighborhoods.{name}")
                candidates = module.generate(
                    solution, self.problem, self.config, self.rng
                )
        else:
            module = import_module(f"topcc.core.neighborhoods.{name}")
            candidates = module.generate(solution, self.problem, self.config, self.rng)
        execution = {
            "sequence": len(self.executions) + 1,
            "neighborhood": name,
            "phase": phase,
            "iteration": iteration,
            "pass": pass_index,
            "candidates_generated": 0,
        }
        self.executions.append(execution)
        with profiling(execution, "generation_seconds"):
            for candidate in islice(candidates, self.config.neighborhood_candidates):
                execution["candidates_generated"] += 1
                yield candidate
