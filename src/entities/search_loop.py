"""Local-search control flow for sampled MOVNS families."""

from typing import TYPE_CHECKING

from .shaking import ruin_recreate

if TYPE_CHECKING:
    from .runner import Runner


def run_iterations(runner: "Runner") -> None:
    """Give each enabled family an independent shake of the same base."""
    for iteration in range(runner.config.max_iterations):
        if runner.exhausted() or not runner.archive.front:
            break
        runner.iterations = iteration + 1
        base = runner.archive.select(iteration, runner.config.front_selection_prob)
        for name in runner.neighborhood.names:
            if runner.exhausted():
                break
            shaken = ruin_recreate(base, runner.config, runner.rng, 1 + iteration // 4)
            perturbed = runner.evaluate(shaken, "ruin_recreate") or base
            for candidate in runner.neighborhood.generate(name, perturbed):
                if runner.exhausted():
                    break
                runner.evaluate(candidate, name)
