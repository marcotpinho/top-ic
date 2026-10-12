"""Local-search control flow for sampled MOVNS families."""

from collections.abc import Iterator
from time import perf_counter
from typing import TYPE_CHECKING

from ..solution import Solution
from .shaking import ruin_recreate

if TYPE_CHECKING:
    from .runner import Runner


def _timed_candidates(
    runner: "Runner", name: str, solution: Solution
) -> Iterator[Solution]:
    """Measure generator work without counting the consumer's evaluation time."""
    candidates = iter(runner.neighborhood.generate(name, solution))
    timing = runner.profile.neighborhoods[name]
    while True:
        started = perf_counter()
        try:
            candidate = next(candidates)
        except StopIteration:
            timing.generation_seconds += perf_counter() - started
            return
        timing.generation_seconds += perf_counter() - started
        yield candidate


def _search_family(runner: "Runner", name: str, base: Solution, iteration: int) -> None:
    """Time one family's shake, candidate generation, and evaluations."""
    timing = runner.profile.neighborhoods[name]
    timing.calls += 1
    started = perf_counter()
    try:
        shake_started = perf_counter()
        shaken = ruin_recreate(base, runner.config, runner.rng, 1 + iteration // 4)
        evaluation_started = perf_counter()
        perturbed = runner.evaluate(shaken, "ruin_recreate") or base
        timing.evaluation_seconds += perf_counter() - evaluation_started
        timing.shake_seconds += perf_counter() - shake_started
        for candidate in _timed_candidates(runner, name, perturbed):
            if runner.exhausted():
                break
            evaluation_started = perf_counter()
            try:
                runner.evaluate(candidate, name)
            finally:
                timing.evaluation_seconds += perf_counter() - evaluation_started
    finally:
        timing.total_seconds += perf_counter() - started


def run_iterations(runner: "Runner") -> None:
    """Time the full local-search loop over independent sampled families."""
    started = perf_counter()
    try:
        for iteration in range(runner.config.max_iterations):
            if runner.exhausted() or not runner.archive.front:
                break
            runner.iterations = iteration + 1
            base = runner.archive.select(iteration, runner.config.front_selection_prob)
            for name in runner.neighborhood.names:
                if runner.exhausted():
                    break
                _search_family(runner, name, base, iteration)
    finally:
        runner.profile.search_loop_seconds += perf_counter() - started
