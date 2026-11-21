"""Batch evaluator with scalar-oracle verification and bounded cache."""

from collections import Counter
from dataclasses import fields, is_dataclass, replace
from hashlib import sha256
from math import inf
from time import perf_counter

import numpy as np

from ...batch.communication import batch_evaluate_communication
from ...batch.tensors import select_trajectories, solutions_to_trajectories
from ...evaluation_core.trajectory import MotionError
from ...solution import Solution
from .Evaluation import Evaluation
from .Evaluator import Evaluator


def _equivalent(first, second, tolerance=1e-9):
    if type(first) is not type(second):
        return False
    if is_dataclass(first):
        return all(
            _equivalent(
                getattr(first, item.name), getattr(second, item.name), tolerance
            )
            for item in fields(first)
        )
    if isinstance(first, (tuple, list)):
        return len(first) == len(second) and all(
            _equivalent(a, b, tolerance) for a, b in zip(first, second)
        )
    if isinstance(first, (float, np.floating)):
        return bool(np.isclose(first, second, rtol=0.0, atol=tolerance, equal_nan=True))
    return first == second


class BatchEvaluator:
    """Evaluate cache misses together while retaining the scalar interface."""

    def __init__(self, problem, config) -> None:
        self.problem = problem
        self.config = config
        self.cache: dict[object, Evaluation] = {}
        self.cache_capacity = config.evaluation_cache_size
        self.route_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.incremental_metrics = Counter()
        self.incremental_divergences = []
        self.batch_metrics = Counter()
        self.verified_keys = set()
        self.scalar = Evaluator(problem, config)
        self.oracle = Evaluator(problem, config)
        self.context = self.scalar.context

    def check_budgets(self, completion_times) -> bool:
        return self.scalar.check_budgets(completion_times)

    def build_trajectories(self, solution: Solution, timing: tuple) -> tuple:
        return self.scalar.build_trajectories(solution, timing)

    def evaluate(self, solution: Solution, parent: Solution | None = None) -> Solution:
        return self.evaluate_batch([solution], [parent])[0]

    def evaluate_batch(
        self,
        solutions: list[Solution],
        parents: list[Solution | None] | None = None,
    ) -> list[Solution]:
        if not solutions:
            return []
        parents = parents or [None] * len(solutions)
        if len(parents) != len(solutions):
            raise ValueError("Parent and solution batch sizes must match")
        results: list[Solution | None] = [None] * len(solutions)
        misses = []
        miss_indices = []
        for index, solution in enumerate(solutions):
            cached = self.cache.get(solution.key)
            if cached is not None:
                self.cache_hits += 1
                results[index] = replace(solution, evaluation=cached)
            else:
                self.cache_misses += 1
                misses.append(solution)
                miss_indices.append(index)
        if misses:
            evaluated = self._evaluate_misses(misses)
            for local_index, scored in enumerate(evaluated):
                global_index = miss_indices[local_index]
                if self._should_verify(scored.key):
                    scored = self.verify(scored)
                self._cache(scored.key, scored.evaluation)
                results[global_index] = scored
        self.batch_metrics["batches"] += 1
        self.batch_metrics["candidates"] += len(solutions)
        self.batch_metrics["maximum_batch_size"] = max(
            self.batch_metrics["maximum_batch_size"], len(solutions)
        )
        if any(result is None for result in results):
            raise RuntimeError("Batch evaluator did not produce every result")
        return list(results)

    def _evaluate_misses(self, solutions: list[Solution]) -> list[Solution]:
        results: list[Solution | None] = [None] * len(solutions)
        valid_solutions = list(solutions)
        valid_indices = list(range(len(solutions)))
        started = perf_counter()
        try:
            trajectories = solutions_to_trajectories(
                valid_solutions,
                self.problem,
                self.route_cache,
                self.config.route_cache_size,
                self.batch_metrics,
            )
        except (MotionError, ValueError):
            valid_solutions = []
            valid_indices = []
            for index, solution in enumerate(solutions):
                try:
                    solutions_to_trajectories(
                        [solution],
                        self.problem,
                        self.route_cache,
                        self.config.route_cache_size,
                        self.batch_metrics,
                    )
                except (MotionError, ValueError) as exc:
                    status = (
                        "unresolved"
                        if type(exc).__name__ == "ContactUncertain"
                        else "invalid"
                    )
                    results[index] = replace(
                        solution,
                        evaluation=Evaluation(
                            False,
                            (inf, inf),
                            (),
                            (),
                            (),
                            str(exc),
                            validation_status=status,
                        ),
                    )
                else:
                    valid_solutions.append(solution)
                    valid_indices.append(index)
            trajectories = (
                solutions_to_trajectories(
                    valid_solutions,
                    self.problem,
                    self.route_cache,
                    self.config.route_cache_size,
                    self.batch_metrics,
                )
                if valid_solutions
                else None
            )
        self.batch_metrics["trajectory_seconds"] += perf_counter() - started
        if not valid_solutions:
            return [result for result in results if result is not None]
        metadata = []
        feasible_local = []
        for local_index, solution in enumerate(valid_solutions):
            visit_times = trajectories.visit_times[local_index]
            reached, owners, reward = self.scalar.credit_rewards(solution, visit_times)
            completions = tuple(
                float(value) for value in trajectories.comp[local_index]
            )
            feasible = self.scalar.check_budgets(completions)
            metadata.append((reached, owners, reward, completions, feasible))
            if feasible:
                feasible_local.append(local_index)
        communication_by_local = {}
        if feasible_local:
            feasible_batch = select_trajectories(trajectories, feasible_local)
            started = perf_counter()
            swept = batch_evaluate_communication(
                feasible_batch,
                self.config.communication_rssi_threshold,
                self.config.recurrence_bound,
                self.batch_metrics,
            )
            self.batch_metrics["communication_seconds"] += perf_counter() - started
            for position, local_index in enumerate(feasible_local):
                communication_by_local[local_index] = (
                    swept.results[position],
                    float(swept.violation[position]),
                    int(swept.status[position]),
                )
        for local_index, solution in enumerate(valid_solutions):
            reached, owners, reward, completions, feasible = metadata[local_index]
            communication = None
            violation = 0.0
            if feasible:
                communication, violation, status = communication_by_local[local_index]
                if status or communication is None:
                    evaluation = self.oracle._safe_evaluate(
                        replace(solution, evaluation=None)
                    )
                    self.batch_metrics["scalar_fallbacks"] += 1
                    results[valid_indices[local_index]] = replace(
                        solution, evaluation=evaluation
                    )
                    continue
            evaluation = self.scalar.assemble_objectives(
                feasible,
                completions,
                reached,
                trajectories.trajectories[local_index],
                trajectories.visit_times[local_index],
                owners,
                reward,
                communication,
                violation,
            )
            results[valid_indices[local_index]] = replace(
                solution, evaluation=evaluation
            )
        return [result for result in results if result is not None]

    def _should_verify(self, key) -> bool:
        if self.config.verify_batch_eval:
            return True
        fraction = self.config.batch_verify_fraction
        if fraction <= 0:
            return False
        digest = sha256(repr(key).encode("utf-8")).digest()
        value = int.from_bytes(digest[:8], "big") & ((1 << 53) - 1)
        return value / float(1 << 53) < fraction

    def verify(self, solution: Solution) -> Solution:
        if solution.key in self.verified_keys and solution.key in self.cache:
            return replace(solution, evaluation=self.cache[solution.key])
        oracle = self.oracle._safe_evaluate(replace(solution, evaluation=None))
        self.batch_metrics["oracle_evaluations"] += 1
        self.verified_keys.add(solution.key)
        self._cache(solution.key, oracle)
        if _equivalent(solution.evaluation, oracle):
            return replace(solution, evaluation=oracle)
        self.batch_metrics["oracle_divergences"] += 1
        if len(self.incremental_divergences) < 20:
            self.incremental_divergences.append({"key": repr(solution.key)})
        return replace(solution, evaluation=oracle)

    def _cache(self, key, evaluation) -> None:
        if key not in self.cache and len(self.cache) >= self.cache_capacity:
            self.cache.pop(next(iter(self.cache)))
            self.batch_metrics["cache_evictions"] += 1
        self.cache[key] = evaluation
