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
            "archive_hypervolume": runner.archive_hypervolume(),
            "hypervolume_reference_point": [1.0, 1.0, 1.0],
            "hypervolume_scales": {
                "total_task_reward": runner.hypervolume_scales()[0],
                "maximum_time_budget_seconds": runner.hypervolume_scales()[1],
            },
            "neighborhood_hv_tau": runner.config.neighborhood_hv_tau,
            "neighborhood_max_passes": runner.config.neighborhood_max_passes,
            "accepted_history": runner.history,
            "objective_history": runner.objective_history,
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
