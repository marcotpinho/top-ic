"""Run result and stable search diagnostics."""

from dataclasses import asdict
from time import perf_counter
from typing import TYPE_CHECKING

from ..runner_models import RunResult

if TYPE_CHECKING:
    from .runner import Runner


def _mean_task_jaccard(runner: "Runner") -> float:
    values = []
    for solution in runner.archive.front:
        reached = solution.evaluation.reached_tasks
        pair_values = []
        for first in range(len(reached)):
            for second in range(first + 1, len(reached)):
                union = reached[first] | reached[second]
                pair_values.append(
                    len(reached[first] & reached[second]) / len(union) if union else 0.0
                )
        if pair_values:
            values.append(sum(pair_values) / len(pair_values))
    return sum(values) / len(values) if values else 0.0


def finish(runner: "Runner", status: str) -> RunResult:
    """Package the current archive, pool, and counters for serialization."""
    statistics = dict(runner.counts)
    front_entries = sum(
        row.get("accepted_front", 0) for row in runner.by_family.values()
    )
    maximum_reward = max(
        (solution.evaluation.reward for solution in runner.archive.front), default=0.0
    )
    best_reward_times = [
        solution.objectives[1]
        for solution in runner.archive.front
        if solution.evaluation.reward == maximum_reward
    ]
    statistics.update(
        {
            "iterations": runner.iterations,
            "operator_counts": {
                name: dict(counts) for name, counts in runner.by_family.items()
            },
            "effective_epsilon": runner.archive.epsilon.epsilon,
            "epsilon_coarsenings": runner.archive.epsilon.coarsenings,
            "archive_hypervolume": runner.archive_hypervolume(),
            "hypervolume_reference_point": [1.0, 1.0],
            "hypervolume_scales": {
                "total_task_reward": runner.hypervolume_scales()[0],
                "maximum_time_budget_seconds": runner.hypervolume_scales()[1],
            },
            "neighborhood_hv_tau": runner.config.neighborhood_hv_tau,
            "neighborhood_max_passes": runner.config.neighborhood_max_passes,
            "accepted_history": runner.history,
            "objective_history": runner.objective_history,
            "metrics_history": runner.metrics_history,
            "selection_history": runner.archive.selection_history,
            "communication_repair_history": runner.repair_history,
            "initialization_history": runner.initialization_history,
            "neighborhood_execution_count": len(runner.neighborhood.executions),
            "neighborhood_executions": list(runner.neighborhood.executions),
            "budget_repairs": list(runner.budget_repairs),
            "pool_size": len(runner.archive.pool),
            "pool": runner.archive.pareto_pool.diagnostics(),
            "pool_base_fraction": (
                sum(row["source"] == "pool" for row in runner.archive.selection_history)
                / len(runner.archive.selection_history)
                if runner.archive.selection_history
                else 0.0
            ),
            "evaluations_per_new_front_member": (
                runner.counts["exact_evaluations"] / front_entries
                if front_entries
                else None
            ),
            "maximum_reward": maximum_reward,
            "minimum_mean_time_at_maximum_reward": min(best_reward_times, default=None),
            "mean_front_task_jaccard": _mean_task_jaccard(runner),
            "rng_seed": runner.config.seed,
            "profiling": asdict(runner.profile),
            "incremental_evaluation": {
                "oracle_evaluations": 0,
                "oracle_divergences": 0,
                **dict(runner.evaluator.incremental_metrics),
                "divergences": list(runner.evaluator.incremental_divergences),
            },
            "parallel_evaluation": {
                "workers": runner.config.evaluation_workers,
                "batch_size": runner.config.evaluation_batch_size,
                "submitted": 0,
                "completed": 0,
                "cancelled": 0,
                "discarded": 0,
                "worker_cache_hits": 0,
                "worker_cache_misses": 0,
                "worker_cache_evictions": 0,
                "worker_cache_peak_entries": 0,
                "worker_peak_rss_bytes": None,
                "worker_rss_unavailable": 0,
                "coordinator_cache_entries": len(runner.evaluator.cache),
                "max_pending": 0,
                **dict(runner.parallel_evaluation.metrics),
            },
        }
    )
    return RunResult(
        runner.problem,
        runner.config,
        list(runner.archive.front),
        statistics,
        perf_counter() - runner.started,
        status,
        (),
        (),
    )
