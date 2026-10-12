"""Epsilon-box front, exact-zero violation layer, and bounded search pool."""

from random import Random

from ..archive import Archive as EpsilonArchive
from ..config import Config
from ..solution import Solution
from .pool import DominatedPool
from .selection import select_base


class Archive:
    def __init__(self, config: Config, rng: Random) -> None:
        self.rng = rng
        self.epsilon = EpsilonArchive(
            config.archive_size,
            config.eps_reward,
            config.eps_time,
            config.violation_resolution,
            zero_separated_last=True,
        )
        self.dominated = DominatedPool(config.dominated_archive_size)

    @property
    def front(self) -> list[Solution]:
        return self.epsilon.front

    @property
    def pool(self) -> list[Solution]:
        return self.dominated.solutions

    def add(self, solution: Solution) -> bool:
        if not solution.evaluation or not solution.evaluation.valid:
            return False
        previous = tuple(self.front)
        retained = self.epsilon.add(solution)
        front_keys = {item.key for item in self.front}
        self.dominated.update([*previous, solution], front_keys)
        return retained

    def select(self, iteration: int, front_probability: float) -> Solution:
        return select_base(
            self.front, self.pool, iteration, front_probability, self.rng
        )
