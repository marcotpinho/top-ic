"""Named neighborhood registry and the single explicit random stream."""

from collections.abc import Iterator
from importlib import import_module
from itertools import islice
from random import Random
from time import perf_counter

from ..config import Config, Problem
from ..solution import Solution

ICC_NEIGHBORHOODS = (
    "remove",
    "replace",
    "assignment",
    "reorder",
    "insert",
    "meeting",
    "relay",
    "unlink",
)


class Neighborhood:
    """Dispatch sampled families without changing their shared interface."""

    ICC = ICC_NEIGHBORHOODS

    def __init__(self, problem: Problem, config: Config, rng: Random) -> None:
        self.problem = problem
        self.config = config
        self.rng = rng
        if config.mode != "team_kop_icc":
            raise ValueError("The rebuilt search supports team_kop_icc only")
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
        module = import_module(f".neighborhoods.{name}", package=__package__)
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
        started = perf_counter()
        try:
            for candidate in islice(candidates, self.config.neighborhood_candidates):
                execution["candidates_generated"] += 1
                yield candidate
        finally:
            execution["generation_seconds"] = perf_counter() - started
