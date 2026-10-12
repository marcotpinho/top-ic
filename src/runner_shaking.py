"""Runner shaking responsibilities."""

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


class RunnerShakingMixin:
    def shake(self, base, strength):
        # One complete ruin-and-recreate attempt is a perturbation. Rebuild
        # prefixes are tried from longest to shortest if budgets reject one.
        for _ in range(min(2, max(1, strength))):
            if self.exhausted():
                break
            mode = self.rng.choice(RUIN_MODES)
            ruined, removed = ruin(base, mode, self.rng, strength)
            if ruined.key == base.key:
                continue
            self.counts["shake_attempts"] += 1
            rebuilt = recreate(ruined, self.problem, self.rng, removed, strength)
            for candidate in (*reversed(rebuilt), ruined):
                if self.exhausted():
                    break
                result = self.evaluate(candidate, "shake:" + mode)
                if result is not None:
                    self.counts["successful_shakes"] += 1
                    return result
        return base
