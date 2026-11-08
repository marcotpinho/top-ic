"""Local-search control flow for sampled MOVNS families."""

from collections.abc import Iterator
from time import perf_counter
from typing import TYPE_CHECKING

from ..solution import Solution
from .communication_repair import repair_communication
from .selection import nondominated, pool_vector, vector_dominates
from .shaking import ruin_recreate

if TYPE_CHECKING:
    from .runner import Runner


def _timed_candidates(
    runner: "Runner",
    name: str,
    solution: Solution,
    iteration: int,
    pass_index: int,
) -> Iterator[Solution]:
    """Measure generator work without counting the consumer's evaluation time."""
    candidates = iter(
        runner.neighborhood.generate(
            name,
            solution,
            iteration=iteration + 1,
            pass_index=pass_index + 1,
        )
    )
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


def _search_family(
    runner: "Runner",
    name: str,
    base: Solution,
    iteration: int,
    pass_index: int,
) -> tuple[float, list[Solution]]:
    """Return CV reduction for an infeasible base, otherwise front hypervolume gain."""
    timing = runner.profile.neighborhoods[name]
    timing.calls += 1
    initial_keys = {solution.key for solution in runner.archive.front}
    initial_hypervolume = runner.archive_hypervolume()
    base_cv = base.evaluation.comm_violation
    best_cv = base_cv
    cv_entrants = []
    started = perf_counter()
    try:
        candidates = list(_timed_candidates(runner, name, base, iteration, pass_index))
        execution = runner.neighborhood.executions[-1]
        evaluated_before = runner.counts["evaluated"]
        for candidate in candidates:
            if runner.exhausted():
                break
            evaluation_started = perf_counter()
            try:
                scored = runner.evaluate(candidate, name)
                if scored is not None and scored.evaluation.valid:
                    cv = scored.evaluation.comm_violation
                    if cv < best_cv:
                        best_cv = cv
                        cv_entrants = [scored]
                    elif cv == best_cv and cv < base_cv:
                        cv_entrants.append(scored)
            finally:
                timing.evaluation_seconds += perf_counter() - evaluation_started
        execution["candidates_evaluated"] = (
            runner.counts["evaluated"] - evaluated_before
        )
    finally:
        timing.total_seconds += perf_counter() - started
    if base_cv > runner.config.numerical_tolerance:
        return base_cv - best_cv, cv_entrants
    entrants = [
        solution
        for solution in runner.archive.front
        if solution.key not in initial_keys
    ]
    improvement = runner.archive_hypervolume() - initial_hypervolume
    return improvement, entrants


def run_iterations(runner: "Runner") -> None:
    """Time the full local-search loop over independent sampled families."""
    started = perf_counter()
    try:
        for iteration in range(runner.config.max_iterations):
            if runner.exhausted() or not (runner.archive.front or runner.archive.pool):
                break
            runner.iterations = iteration + 1
            base = runner.archive.select(iteration)
            runner.active_base = base
            runner.active_base_source = runner.archive.selection_history[-1]["source"]
            initial_front_keys = {solution.key for solution in runner.archive.front}
            initial_pool_vectors = {
                pool_vector(solution)
                for solution in nondominated(runner.archive.pool, pool_vector)
            }
            shaken = ruin_recreate(base, runner.config, runner.rng, 1 + iteration // 4)
            working = runner.evaluate(shaken, "ruin_recreate")
            if working is None:
                working = base
            if (
                working.evaluation.valid
                and working.evaluation.comm_violation
                > runner.config.numerical_tolerance
            ):
                working = repair_communication(runner, working)
            for name in runner.neighborhood.names:
                if runner.exhausted():
                    break
                pass_base = working
                for pass_index in range(runner.config.neighborhood_max_passes):
                    if runner.exhausted():
                        break
                    threshold = (
                        runner.config.numerical_tolerance
                        if pass_base.evaluation.comm_violation # Is from unfeasible base, so we want to reduce CV
                        > runner.config.numerical_tolerance
                        else runner.config.neighborhood_hv_tau # Is from feasible base, so we want to improve hypervolume
                    )
                    improvement, entrants = _search_family(
                        runner, name, pass_base, iteration, pass_index
                    )
                    if improvement <= threshold or not entrants:
                        break
                    working = pass_base = runner.rng.choice(entrants)
            new_front = any(
                solution.key not in initial_front_keys
                for solution in runner.archive.front
            )
            pool_improvement = any(
                vector not in initial_pool_vectors
                and not any(
                    vector_dominates(previous, vector)
                    for previous in initial_pool_vectors
                )
                for vector in (
                    pool_vector(solution)
                    for solution in nondominated(runner.archive.pool, pool_vector)
                )
            )
            runner.archive.mark_expansion(base, new_front or pool_improvement)
            runner.active_base = None
            runner.active_base_source = None
            runner.record_archive_objectives(iteration + 1)
            runner.record_metrics(iteration + 1)
    finally:
        runner.profile.search_loop_seconds += perf_counter() - started
