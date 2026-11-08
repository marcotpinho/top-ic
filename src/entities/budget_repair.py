"""Restore flight budgets by dropping visits at minimum reward/time loss."""

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..evaluation_core.scheduling import schedule
from ..evaluation_core.trajectory import MotionError, State, connect
from ..solution import Solution
from .neighborhoods.common import edited
from .profiling import profiling

if TYPE_CHECKING:
    from .runner import Runner


@dataclass(frozen=True)
class RoutePreview:
    """Route completion times and cached durations of consecutive connections."""

    completion_times: tuple[float, ...]
    connection_times: tuple[tuple[float, ...], ...]


def preview_solution(runner: "Runner", solution: Solution) -> RoutePreview:
    """Compute route times once without reward or communication evaluation."""
    with profiling(runner.profile, "budget_precheck_seconds"):
        timing, durations = schedule(solution.routes, runner.problem)
        return RoutePreview(tuple(route[-1][0] for route in timing), durations)


def _preview_removal(
    runner: "Runner", solution: Solution, current: RoutePreview, agent: int, index: int
) -> RoutePreview:
    with profiling(runner.profile, "budget_precheck_seconds"):
        route = solution.routes[agent]
        before, after = route[index - 1], route[index + 1]
        duration = connect(
            State(before.position, before.velocity),
            State(after.position, after.velocity),
            runner.problem.limits[agent],
        ).duration
        old = current.connection_times[agent]
        completions = list(current.completion_times)
        completions[agent] += duration - old[index - 1] - old[index]
        durations = list(current.connection_times)
        durations[agent] = (*old[: index - 1], duration, *old[index + 1 :])
        return RoutePreview(tuple(completions), tuple(durations))


def _drop_choices(
    runner: "Runner", solution: Solution, current: RoutePreview
) -> list[tuple[float, float, float, int, int, Solution, RoutePreview]]:
    """Rank TASK and FREE deletions by team reward lost per saved second."""
    choices: list[tuple[float, float, float, int, int, Solution, RoutePreview]] = []
    task_counts = Counter(
        visit.task_id
        for route in solution.routes
        for visit in route
        if visit.kind == "TASK"
    )
    rewards = {task.id: task.reward for task in runner.problem.tasks}
    for agent, route in enumerate(solution.routes):
        budget = runner.problem.time_budgets[agent]
        if current.completion_times[agent] <= budget + runner.config.budget_tolerance:
            continue
        for visit_index, visit in enumerate(route[1:-1], 1):
            if runner.exhausted():
                return choices
            if visit.kind not in ("TASK", "FREE"):
                continue
            candidate_route = (*route[:visit_index], *route[visit_index + 1 :])
            candidate = edited(solution, agent, candidate_route)
            try:
                preview = _preview_removal(
                    runner, solution, current, agent, visit_index
                )
            except (MotionError, ValueError):
                preview = None
            finally:
                runner.counts["budget_repair_probes"] += 1
            if preview is None:
                continue
            time_saved = (
                current.completion_times[agent] - preview.completion_times[agent]
            )
            if time_saved <= runner.config.budget_tolerance:
                continue
            reward_lost = (
                rewards[visit.task_id]
                if visit.kind == "TASK" and task_counts[visit.task_id] == 1
                else 0.0
            )
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
    runner: "Runner", solution: Solution, preview: RoutePreview
) -> tuple[Solution | None, dict]:
    """Drop TASK or FREE visits until each flight budget fits.

    At each step, remove the feasible visit occurrence with minimum team reward
    lost per second saved on an over-budget route. Duplicate task occurrences
    have zero team reward loss while another route still serves that task;
    FREE deletions always have zero reward loss.
    Exact evaluator scheduling and continuous connectors determine each saving.
    """
    with profiling(runner.profile, "budget_repair_seconds"):
        current_solution = solution
        current = preview
        dropped: list[str] = []
        free_dropped: list[str] = []
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
            _, reward_lost, _, agent, visit_index, candidate, candidate_preview = min(
                choices
            )
            visit = current_solution.routes[agent][visit_index]
            if visit.kind == "TASK":
                dropped.append(visit.task_id)
            else:
                free_dropped.append(visit.id)
            total_reward_lost += reward_lost
            current_solution, current = candidate, candidate_preview
        within_budgets = all(
            completion <= budget + runner.config.budget_tolerance
            for completion, budget in zip(
                current.completion_times, runner.problem.time_budgets
            )
        )
    record = {
        "initial_completion_times": list(preview.completion_times),
        "final_completion_times": list(current.completion_times),
        "tasks_dropped": dropped,
        "free_waypoints_dropped": free_dropped,
        "team_reward_lost": total_reward_lost,
        "within_budgets": within_budgets,
    }
    return (current_solution if within_budgets else None), record
