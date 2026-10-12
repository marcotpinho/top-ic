"""Shared candidate sampling and occurrence-safe route edits."""

from collections.abc import Iterable
from random import Random

from ...neighborhoods.common import (
    edited,
    fresh_id,
    in_workspace,
    normalize,
    reached_task_ids,
    segment_projection,
    unreached_tasks,
)


def sample_candidates[Candidate](
    proposals: Iterable[Candidate], rng: Random, cap: int
) -> list[Candidate]:
    """Uniformly sample at most cap proposals with O(cap) memory."""
    chosen: list[Candidate] = []
    for count, proposal in enumerate(proposals, 1):
        if len(chosen) < cap:
            chosen.append(proposal)
        else:
            index = rng.randrange(count)
            if index < cap:
                chosen[index] = proposal
    rng.shuffle(chosen)
    return chosen


__all__ = [
    "edited",
    "fresh_id",
    "in_workspace",
    "normalize",
    "reached_task_ids",
    "sample_candidates",
    "segment_projection",
    "unreached_tasks",
]
