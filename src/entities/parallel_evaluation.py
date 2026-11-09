"""Ordered VND evaluation with coordinator-owned search state."""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor, TimeoutError
from dataclasses import replace
from multiprocessing import get_context
from sys import platform
from time import perf_counter

from .archive_updates import evaluate_candidate, integrate_candidate, prepare_candidate
from .evaluator import Evaluator
from .profiling import profiling

_worker_evaluator = None


def _initialize_worker(problem, config):
    global _worker_evaluator
    _worker_evaluator = Evaluator(problem, config)


def _peak_rss_bytes():
    if platform != "darwin" and not platform.startswith("linux"):
        return None
    try:
        from resource import RUSAGE_SELF, getrusage

        peak = getrusage(RUSAGE_SELF).ru_maxrss
        return int(peak if platform == "darwin" else peak * 1024)
    except (ImportError, OSError, ValueError):
        return None


def _evaluate_worker(candidate, parent):
    evaluator = _worker_evaluator
    before = evaluator.incremental_metrics.copy()
    hits, misses = evaluator.cache_hits, evaluator.cache_misses
    evaluator.incremental_divergences.clear()
    started = perf_counter()
    scored = evaluator.evaluate(candidate, parent=parent)
    elapsed = perf_counter() - started
    delta = {
        name: value - before[name]
        for name, value in evaluator.incremental_metrics.items()
    }
    return (
        scored,
        elapsed,
        delta,
        list(evaluator.incremental_divergences),
        evaluator.cache_hits - hits,
        evaluator.cache_misses - misses,
        len(evaluator.cache),
        _peak_rss_bytes(),
    )


class ParallelEvaluation:
    def __init__(self, runner):
        self.runner = runner
        self.executor = None
        self.metrics = Counter()

    def _executor(self):
        if self.executor is None:
            runner = self.runner
            self.executor = ProcessPoolExecutor(
                max_workers=runner.config.evaluation_workers,
                mp_context=get_context("spawn"),
                initializer=_initialize_worker,
                initargs=(runner.problem, runner.config),
            )
        return self.executor

    def close(self):
        if self.executor is not None:
            self.executor.shutdown(wait=True, cancel_futures=True)
            self.executor = None

    def evaluate_batch(self, candidates, family, parent):
        runner = self.runner
        if runner.config.evaluation_workers == 1:
            results = []
            for candidate in candidates:
                if runner.exhausted():
                    break
                results.append(evaluate_candidate(runner, candidate, family, parent))
            return results
        limit = min(
            runner.config.evaluation_batch_size, 2 * runner.config.evaluation_workers
        )
        candidates = iter(candidates)
        results = []
        done = False
        while not done and not runner.exhausted():
            pending = []
            try:
                while len(pending) < limit and not runner.exhausted():
                    candidate = next(candidates, None)
                    if candidate is None:
                        done = True
                        break
                    prepared = prepare_candidate(runner, candidate, family)
                    if prepared is None:
                        continue
                    candidate, row, repair_row = prepared
                    cached = runner.evaluator.cache.get(candidate.key)
                    miss = cached is None
                    runner.reserved_evaluations += int(miss)
                    future = None
                    if miss:
                        with profiling(runner.profile, "parallel_dispatch_seconds"):
                            future = self._executor().submit(
                                _evaluate_worker,
                                replace(candidate, evaluation=None),
                                parent,
                            )
                        self.metrics["submitted"] += 1
                    pending.append((candidate, row, repair_row, future, cached, miss))
                self.metrics["max_pending"] = max(
                    self.metrics["max_pending"], len(pending)
                )
                for index, (
                    candidate,
                    row,
                    repair_row,
                    future,
                    cached,
                    miss,
                ) in enumerate(pending):
                    remaining = runner.config.max_seconds - (
                        perf_counter() - runner.started
                    )
                    if remaining <= 0:
                        done = True
                        self._discard(pending[index:])
                        break
                    if future is None:
                        scored = replace(candidate, evaluation=cached)
                    else:
                        try:
                            with (
                                profiling(runner.profile, "evaluator_seconds"),
                                profiling(runner.profile, "parallel_wait_seconds"),
                            ):
                                outcome = future.result(timeout=remaining)
                        except TimeoutError:
                            if future.done() and not future.cancelled():
                                error = future.exception()
                                if error is not None:
                                    raise error
                            done = True
                            self._discard(pending[index:])
                            break
                        if perf_counter() - runner.started >= runner.config.max_seconds:
                            done = True
                            self._discard(pending[index:])
                            break
                        (
                            scored,
                            elapsed,
                            delta,
                            divergences,
                            hits,
                            misses,
                            cache_size,
                            peak_rss,
                        ) = outcome
                        self.metrics["completed"] += 1
                        self.metrics["worker_cache_hits"] += hits
                        self.metrics["worker_cache_misses"] += misses
                        runner.profile.worker_evaluator_seconds += elapsed
                        runner.profile.oracle_seconds += delta.get(
                            "oracle_seconds", 0.0
                        )
                        self.metrics["worker_cache_evictions"] += delta.pop(
                            "evaluation_cache_evictions", 0
                        )
                        self.metrics["worker_cache_peak_entries"] = max(
                            self.metrics["worker_cache_peak_entries"], cache_size
                        )
                        if peak_rss is not None:
                            self.metrics["worker_peak_rss_bytes"] = max(
                                self.metrics["worker_peak_rss_bytes"], peak_rss
                            )
                        else:
                            self.metrics["worker_rss_unavailable"] += 1
                        runner.evaluator.incremental_metrics.update(delta)
                        slots = max(
                            0, 20 - len(runner.evaluator.incremental_divergences)
                        )
                        runner.evaluator.incremental_divergences.extend(
                            divergences[:slots]
                        )
                        cache = runner.evaluator.cache
                        if len(cache) >= runner.evaluator.cache_capacity:
                            cache.pop(next(iter(cache)))
                            runner.evaluator.incremental_metrics[
                                "evaluation_cache_evictions"
                            ] += 1
                        cache[candidate.key] = scored.evaluation
                    runner.reserved_evaluations -= int(miss)
                    evaluation_row = repair_row if repair_row is not None else row
                    with profiling(runner.profile, "candidate_counters_seconds"):
                        runner.evaluator.cache_misses += int(miss)
                        runner.evaluator.cache_hits += int(not miss)
                        for counters in (runner.counts, evaluation_row):
                            counters["evaluated"] += 1
                            counters["exact_evaluations"] += int(miss)
                            counters["cache_hits"] += int(not miss)
                    results.append(
                        integrate_candidate(runner, scored, family, row, repair_row)
                    )
            except BaseException:
                for _, _, _, future, _, _ in pending:
                    if future is not None:
                        future.cancel()
                raise
            finally:
                runner.reserved_evaluations = 0
        return results

    def _discard(self, pending):
        self.metrics["discarded"] += len(pending)
        for _, _, _, future, _, _ in pending:
            if future is not None and future.cancel():
                self.metrics["cancelled"] += 1
