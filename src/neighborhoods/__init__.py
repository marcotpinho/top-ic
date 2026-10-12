"""Named neighborhood generators with explicit random streams."""

from importlib import import_module
from random import Random
from typing import Iterator

from ..config import Config, Problem
from ..solution import Solution
from .registry import (
    COMM_NEIGHBORHOODS,
    ICC_NEIGHBORHOODS,
    SINGLE_NEIGHBORHOODS,
    TEAM_NEIGHBORHOODS,
)


def generate(
    name: str,
    solution: Solution,
    problem: Problem,
    config: Config,
    rng: Random,
    **kwargs: object,
) -> Iterator[Solution]:
    """Dispatch a named family without changing its enumeration order."""
    module_path = (
        f"{__name__}.legacy.{name}"
        if name
        in (
            "wait",
            "free_move",
            "free_remove",
            "duplicate_rendezvous",
            "velocity",
            "velocity_dp",
        )
        else f"{__name__}.{name}"
    )
    module = import_module(module_path)
    yield from module.generate(solution, problem, config, rng, **kwargs)
