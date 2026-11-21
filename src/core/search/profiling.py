"""Wall-clock accumulators for the ICC search.

All durations use perf_counter seconds. Family total includes shaking,
generation, and evaluation. The shake duration covers perturbation only;
its later candidate evaluation is included in evaluation_seconds.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter

@contextmanager
def profiling(target, field: str) -> Iterator[None]:
    started = perf_counter()
    try:
        yield
    finally:
        elapsed = perf_counter() - started
        if isinstance(target, dict):
            target[field] = target.get(field, 0.0) + elapsed
        else:
            setattr(target, field, getattr(target, field) + elapsed)


from ...entities.search.NeighborhoodTiming import NeighborhoodTiming
from ...entities.search.SearchProfile import SearchProfile


__all__ = ["NeighborhoodTiming", "SearchProfile", "profiling"]
