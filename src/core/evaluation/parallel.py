from sys import platform
from time import perf_counter

from ...entities.evaluation.Evaluator import Evaluator

_worker_evaluator = None


def initialize_worker(problem, config):
    global _worker_evaluator
    _worker_evaluator = Evaluator(problem, config)


def peak_rss_bytes():
    if platform != "darwin" and not platform.startswith("linux"):
        return None
    try:
        from resource import RUSAGE_SELF, getrusage

        peak = getrusage(RUSAGE_SELF).ru_maxrss
        return int(peak if platform == "darwin" else peak * 1024)
    except (ImportError, OSError, ValueError):
        return None


def evaluate_worker(candidate, parent):
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
        peak_rss_bytes(),
    )
