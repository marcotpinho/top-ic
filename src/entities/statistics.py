"""Run result and stable search diagnostics."""

from dataclasses import asdict
from time import perf_counter
from typing import TYPE_CHECKING

from ..runner_models import RunResult

if TYPE_CHECKING:
    from .runner import Runner


def finish(runner: "Runner", status: str) -> RunResult:
    """Package the current archive, pool, and counters for serialization."""
    statistics = dict(runner.counts)
    statistics.update(
        {
            "iterations": runner.iterations,
            "operator_counts": {
                name: dict(counts) for name, counts in runner.by_family.items()
            },
            "effective_epsilon": runner.archive.epsilon.epsilon,
            "epsilon_coarsenings": runner.archive.epsilon.coarsenings,
            "accepted_history": runner.history,
            "pool_size": len(runner.archive.pool),
            "rng_seed": runner.config.seed,
            "profiling": asdict(runner.profile),
        }
    )
    return RunResult(
        runner.problem,
        runner.config,
        list(runner.archive.front),
        statistics,
        perf_counter() - runner.started,
        status,
        tuple(runner.archive.pool[: runner.config.candidate_bank_size]),
        tuple(runner.archive.pool),
    )
