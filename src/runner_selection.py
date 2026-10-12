"""Runner selection responsibilities."""

"""Budgeted MOVNS/VND plus a matched KOP-inspired LNS baseline."""
from dataclasses import dataclass, replace
from collections import defaultdict
from itertools import combinations, islice
from time import perf_counter
from math import hypot
import random
from .archive import Archive
from .dominated_archive import DominatedArchive, repair_coordinates
from .evaluator import Evaluator
from .solution import direct_solution
from .operators import normalize
from .neighborhoods import (
    generate,
    SINGLE_NEIGHBORHOODS,
    TEAM_NEIGHBORHOODS,
    ICC_NEIGHBORHOODS,
)
from .perturbation import RUIN_MODES, ruin, recreate
from .velocity_dp import refine_route_velocities
from .runner_models import RunResult


class RunnerSelectionMixin:
    def select_seed(self, iteration):
        """Visit every live archive member before repeating, alternating objectives."""
        front = self.archive.front + self.archive.alternatives
        dominated = self.dominated.solutions if self.icc else []
        choose_front = bool(front) and (
            not dominated or self.rng.random() < self.config.front_selection_prob
        )
        source = "front" if choose_front else "dominated"
        pool = front if choose_front else dominated
        if not pool:
            source = "front"
            pool = front
        live = {s.key for s in pool}
        visited = self.visited_seeds[source]
        visited.intersection_update(live)
        unexplored = [s for s in pool if s.key not in visited]
        if not unexplored:
            visited.clear()
            unexplored = pool[:]
        criterion = (
            ("reward", "violation", "repair", "time")[iteration % 4]
            if self.icc
            else ("reward" if iteration % 2 == 0 else "time")
        )
        if criterion == "reward":
            key = lambda s: (-s.evaluation.reward, s.objectives[1], repr(s.key))
        elif criterion == "violation":
            key = lambda s: (
                s.objectives[2],
                s.objectives[1],
                -s.evaluation.reward,
                repr(s.key),
            )
        elif criterion == "repair":
            key = lambda s: (
                s.objectives[2] == 0,
                repair_coordinates(s)[0] if s.objectives[2] > 0 else s.objectives[1],
                repair_coordinates(s)[1],
                -s.evaluation.reward,
                repr(s.key),
            )
        else:
            key = lambda s: (s.objectives[1], -s.evaluation.reward, repr(s.key))
        # Ranked sampling keeps the criterion influential without always restarting at its extreme.
        ranked = sorted(unexplored, key=key)
        weights = range(len(ranked), 0, -1)
        selected = self.rng.choices(ranked, weights=weights, k=1)[0]
        visited.add(selected.key)
        self.seed_selection_history.append(
            {
                "iteration": iteration + 1,
                "source": source,
                "criterion": criterion,
                "objectives": selected.objectives,
                "key": repr(selected.key),
            }
        )
        return selected

    def candidate_stream(self, base, family):
        """Use a fresh seeded order and share each family cap across agents/pairs."""
        order = list(range(len(base.routes)))
        self.rng.shuffle(order)
        if family in ("reorder", "insert", "remove", "replace", "assignment"):
            yield from generate(
                family, base, self.problem, self.config, self.rng, agent_order=order
            )
            return
        elif (
            self.icc
            and family in ("excursion", "meeting", "unlink")
            and len(base.routes) > 1
        ):
            pairs = list(combinations(range(len(base.routes)), 2))
            self.rng.shuffle(pairs)
            bottleneck = (
                base.evaluation.communication.bottleneck
                if base.evaluation and base.evaluation.communication
                else None
            )
            if bottleneck:
                pairs.sort(key=lambda p: p != tuple(sorted(bottleneck[:2])))
            streams = [
                iter(
                    generate(
                        family,
                        base,
                        self.problem,
                        self.config,
                        self.rng,
                        pair_filter=pair,
                    )
                )
                for pair in pairs
            ]
        else:
            yield from generate(
                family, base, self.problem, self.config, self.rng, agent_order=order
            )
            return
        while streams:
            remaining = []
            for stream in streams:
                try:
                    yield next(stream)
                except StopIteration:
                    continue
                remaining.append(stream)
            streams = remaining
