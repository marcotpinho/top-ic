"""Restore flight budgets by dropping tasks at minimum reward/time loss."""

from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING

from ..evaluation_core.trajectory import MotionError
from ..solution import Solution
from .neighborhoods.common import edited

if TYPE_CHECKING:
    from .runner import Runner


@dataclass(frozen=True)
class RoutePreview:
    """Reward and exact route completion times without communication scoring."""

    reward: float
    completion_times: tuple[float, ...]


def _preview(runner: "Runner", solution: Solution) -> RoutePreview | None:
    """Build exact schedules and routes for a reward/time repair comparison."""
    evaluator = runner.evaluator
    evaluator.validate_structure(solution)
    timing = evaluator.schedule_solution(solution)
    trajectories, visit_times = evaluator.build_trajectories(solution, timing)
    _, _, reward = evaluator.credit_rewards(solution, visit_times)
    return RoutePreview(reward, tuple(route.completion_time for route in trajectories))


def _drop_choices(
    runner: "Runner", solution: Solution, current: RoutePreview
) -> list[tuple[float, float, float, int, int, Solution, RoutePreview]]:
    """Rank feasible single TASK deletions by team reward lost per saved second."""
    choices: list[tuple[float, float, float, int, int, Solution, RoutePreview]] = []
    for agent, route in enumerate(solution.routes):
        budget = runner.problem.time_budgets[agent]
        if current.completion_times[agent] <= budget + runner.config.budget_tolerance:
            continue
        for visit_index, visit in enumerate(route[1:-1], 1):
            if runner.exhausted():
                return choices
            if visit.kind != "TASK":
                continue
            candidate_route = (*route[:visit_index], *route[visit_index + 1 :])
            candidate = edited(solution, agent, candidate_route)
            started = perf_counter()
            try:
                preview = _preview(runner, candidate)
            except (MotionError, ValueError):
                preview = None
            finally:
                runner.profile.evaluator_seconds += perf_counter() - started
                runner.counts["budget_repair_probes"] += 1
            if preview is None:
                continue
            time_saved = (
                current.completion_times[agent] - preview.completion_times[agent]
            )
            if time_saved <= runner.config.budget_tolerance:
                continue
            reward_lost = max(0.0, current.reward - preview.reward)
            ratio = reward_lost / time_saved
            choices.append(
                (
                    ratio,
                    reward_lost,
                    -time_saved,
                    agent,
                    visit_index,
                    candidate,
                    preview,
                )
            )
    return choices


def repair_over_budget(
    runner: "Runner", solution: Solution
) -> tuple[Solution | None, dict]:
    """Drop TASK visits until each flight budget fits; leave FREE visits intact.

    At each step, remove the feasible TASK occurrence with minimum team reward
    lost per second saved on an over-budget route. Duplicate task occurrences
    have zero team reward loss while another route still serves that task.
    Exact evaluator scheduling and continuous connectors determine each saving.
    """
    started = perf_counter()
    current_solution = solution
    current = RoutePreview(
        solution.evaluation.reward,
        tuple(solution.evaluation.completion_times),
    )
    dropped: list[str] = []
    total_reward_lost = 0.0
    while any(
        completion > budget + runner.config.budget_tolerance
        for completion, budget in zip(
            current.completion_times, runner.problem.time_budgets
        )
    ):
        if runner.exhausted():
            break
        choices = _drop_choices(runner, current_solution, current)
        if not choices:
            break
        _, reward_lost, _, agent, visit_index, candidate, preview = min(choices)
        dropped.append(current_solution.routes[agent][visit_index].task_id)
        total_reward_lost += reward_lost
        current_solution, current = candidate, preview
    within_budgets = all(
        completion <= budget + runner.config.budget_tolerance
        for completion, budget in zip(
            current.completion_times, runner.problem.time_budgets
        )
    )
    runner.profile.budget_repair_seconds += perf_counter() - started
    record = {
        "initial_completion_times": list(solution.evaluation.completion_times),
        "final_completion_times": list(current.completion_times),
        "tasks_dropped": dropped,
        "team_reward_lost": total_reward_lost,
        "within_budgets": within_budgets,
    }
    return (current_solution if within_budgets else None), record
