"""Validate a solution and assemble the TOP-ICC objectives in ordered stages."""

from dataclasses import dataclass, replace
from itertools import pairwise
from math import inf

from ..config import Config, Problem
from ..solution import Solution, Visit
from .communication import evaluate_communication
from .scheduling import schedule
from .trajectory import AgentTrajectory, MotionError, State, connect


@dataclass(frozen=True)
class Evaluation:
    valid: bool
    objectives: tuple[float, ...]
    completion_times: tuple[float, ...]
    reached_tasks: tuple[frozenset[str], ...]
    trajectories: tuple[AgentTrajectory, ...]
    reason: str = ""
    peak_staleness: float | None = None
    first_visitors: tuple[tuple[str, int, float], ...] = ()
    motion_budget_valid: bool = False
    comm_violation: float = 0.0
    communication: object = None
    visit_times: tuple = ()
    validation_status: str = "valid"

    @property
    def reward(self) -> float:
        """Return Q, the reward in eq. (7); evaluation is immutable."""
        return -self.objectives[0]


class Evaluator:
    """Cache complete evaluations by physical solution identity."""

    def __init__(self, problem: Problem, config: Config) -> None:
        self.problem = problem
        self.config = config
        self.cache: dict[object, Evaluation] = {}
        self.cache_hits = 0
        self.cache_misses = 0

    def evaluate(self, solution: Solution) -> Solution:
        """Return a scored immutable solution; invalid input has infinite objectives."""
        key = solution.key
        if key in self.cache:
            self.cache_hits += 1
            return replace(solution, evaluation=self.cache[key])
        self.cache_misses += 1
        try:
            result = self._evaluate(solution)
        except (MotionError, ValueError) as exc:
            status = (
                "unresolved" if type(exc).__name__ == "ContactUncertain" else "invalid"
            )
            result = Evaluation(
                False, (inf, inf), (), (), (), str(exc), validation_status=status
            )
        self.cache[key] = result
        return replace(solution, evaluation=result)

    def _evaluate(self, solution: Solution) -> Evaluation:
        """Build trajectories and assemble objectives; implements eqs. (1)–(15)."""
        timing = self.schedule_solution(solution)
        trajectories, visit_times = self.build_trajectories(solution, timing)
        reached, owners, reward = self.credit_rewards(solution, visit_times)
        completions = tuple(trajectory.completion_time for trajectory in trajectories)
        feasible = self.check_budgets(completions)
        communication, violation = self.evaluate_links(trajectories, feasible)
        return self.assemble_objectives(
            feasible,
            completions,
            reached,
            trajectories,
            visit_times,
            owners,
            reward,
            communication,
            violation,
        )

    def schedule_solution(self, solution: Solution) -> tuple:
        """Schedule fixed route connection durations; implements eq. (2)."""
        timing, _ = schedule(
            solution.routes,
            self.problem,
        )
        return timing

    def build_trajectories(
        self, solution: Solution, timing: tuple
    ) -> tuple[tuple, tuple]:
        """Construct piecewise motion and visit times; implements eqs. (2)–(6)."""
        trajectories = []
        visit_times = []
        for agent, route in enumerate(solution.routes):
            trajectory, times = self._build_route_trajectory(agent, route, timing)
            trajectories.append(trajectory)
            visit_times.append(times)
        return tuple(trajectories), tuple(visit_times)

    def _build_route_trajectory(
        self, agent: int, route: tuple[Visit, ...], timing: tuple
    ) -> tuple:
        """Connect consecutive visits without pauses, eqs. (1)–(4)."""
        pieces = []
        elapsed = 0.0
        times = []
        for visit_index, (start, end) in enumerate(pairwise(route)):
            times.append(timing[agent][visit_index])
            connection = connect(
                State(start.position, start.velocity),
                State(end.position, end.velocity),
                self.problem.limits[agent],
            )
            pieces.extend(
                replace(piece, start_time=piece.start_time + elapsed)
                for piece in connection.pieces
            )
            elapsed += connection.duration
        times.append((elapsed, elapsed))
        trajectory = AgentTrajectory(
            tuple(pieces),
            elapsed,
            State(route[0].position, route[0].velocity),
            State(route[-1].position, route[-1].velocity),
        )
        return trajectory, tuple(times)

    def credit_rewards(self, solution: Solution, visit_times: tuple) -> tuple:
        """Credit unique task IDs and first arrivals; implements eq. (7)."""
        reached = []
        owners = {}
        for agent, route in enumerate(solution.routes):
            tasks = set()
            for visit_index, visit in enumerate(route):
                if visit.kind != "TASK":
                    continue
                tasks.add(visit.task_id)
                record = (visit_times[agent][visit_index][0], agent)
                if visit.task_id not in owners or record < owners[visit.task_id]:
                    owners[visit.task_id] = record
            reached.append(frozenset(tasks))
        unique_tasks = set().union(*reached)
        reward = sum(
            task.reward for task in self.problem.tasks if task.id in unique_tasks
        )
        return tuple(reached), owners, reward

    def check_budgets(self, completions: tuple[float, ...]) -> bool:
        """Check individual completion against B_m; implements eq. (5)."""
        tolerance = self.config.budget_tolerance
        return all(
            completion <= budget + tolerance
            for completion, budget in zip(completions, self.problem.time_budgets)
        )

    def evaluate_links(
        self, trajectories: tuple, feasible: bool
    ) -> tuple[object | None, float]:
        """Evaluate contacts and ordered-pair constraint violation; eqs. (9)–(15)."""
        if not feasible:
            return None, 0.0
        communication = evaluate_communication(
            trajectories,
            self.config.comm_range,
            self.config.recurrence_bound,
        )
        violation = sum(
            max(0.0, peak - self.config.recurrence_bound)
            for receiver, row in enumerate(communication.pair_peaks)
            for source, peak in enumerate(row)
            if receiver != source
        )
        return communication, violation

    def assemble_objectives(
        self,
        feasible: bool,
        completions: tuple,
        reached: tuple,
        trajectories: tuple,
        visit_times: tuple,
        owners: dict,
        reward: float,
        communication: object | None,
        violation: float,
    ) -> Evaluation:
        """Assemble the two reported minimization objectives and separate CV."""
        objectives = (
            -reward,
            sum(completions) / len(completions),
        )
        first_visitors = tuple(
            (task, agent, time) for task, (time, agent) in sorted(owners.items())
        )
        peak = communication.peak_staleness if communication else None
        reason = "" if feasible else "Individual flight-time budget exceeded"
        return Evaluation(
            feasible,
            objectives,
            completions,
            reached,
            trajectories,
            reason,
            peak,
            first_visitors,
            feasible,
            violation,
            communication,
            visit_times,
        )
