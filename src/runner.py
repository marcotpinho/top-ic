"""Budgeted MOVNS/VND and KOP-inspired LNS orchestration."""

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


from .runner_seeds import RunnerSeedsMixin
from .runner_selection import RunnerSelectionMixin
from .runner_shaking import RunnerShakingMixin
from .runner_search import RunnerSearchMixin
from .runner_archive import RunnerArchiveMixin
from .runner_statistics import RunnerStatisticsMixin


class Runner(
    RunnerSeedsMixin,
    RunnerSelectionMixin,
    RunnerShakingMixin,
    RunnerSearchMixin,
    RunnerArchiveMixin,
    RunnerStatisticsMixin,
):
    def __init__(self, problem, config, allow_team=False):
        self.problem = problem
        self.config = config
        self.evaluator = Evaluator(problem, allow_team=allow_team, config=config)
        self.icc = config.mode == "team_kop_icc"
        self.dominated = DominatedArchive(config.dominated_archive_size)
        self.bank = []
        self.bank_seen = 0
        self.archive = Archive(
            config.archive_size,
            config.eps_reward,
            config.eps_time,
            config.violation_resolution if self.icc else None,
            zero_separated_last=self.icc,
        )
        self.rng = random.Random(config.seed)
        self.counts = defaultdict(int)
        self.operator_counts = defaultdict(lambda: defaultdict(int))
        self.seen = set()
        self.started = 0.0
        self.iterations = 0
        families = (
            ICC_NEIGHBORHOODS
            if self.icc
            else TEAM_NEIGHBORHOODS
            if allow_team
            else SINGLE_NEIGHBORHOODS
        )
        self.families = tuple(n for n in families if n not in config.disabled)
        self.log = []
        self.objective_history = []
        self.archive_history = []
        self.visited_seeds = {"front": set(), "dominated": set()}
        self.seed_selection_history = []
        self.velocity_cache = {}
        self.refinement_comparison = defaultdict(lambda: defaultdict(int))
        self.connectivity_diagnostics = defaultdict(lambda: defaultdict(int))
        self.current_parent = None
