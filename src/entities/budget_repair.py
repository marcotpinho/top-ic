"""Restore flight budgets by dropping visits at minimum reward/time loss."""

from collections import Counter
from dataclasses import dataclass
from itertools import accumulate
from typing import TYPE_CHECKING

from ..evaluation_core.scheduling import schedule
from ..evaluation_core.trajectory import MotionError, State, connect
from ..solution import Solution
from .budget_communication import preserves_local_contacts
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
    runner: "Runner", solution: Solution, current: RoutePreview, kind: str
) -> list[tuple[float, float, float, int, int, Solution, RoutePreview]]:
    """Rank removals within the current FREE or TASK repair phase."""
    choices: list[tuple[float, float, float, int, int, Solution, RoutePreview]] = []
    task_counts = Counter(
        visit.task_id
        for route in solution.routes
        for visit in route
        if visit.kind == "TASK"
    )
    rewards = {task.id: task.reward for task in runner.problem.tasks}
    trajectories = None
    for agent, route in enumerate(solution.routes):
        budget = runner.problem.time_budgets[agent]
        if current.completion_times[agent] <= budget + runner.config.budget_tolerance:
            continue
        for visit_index, visit in enumerate(route[1:-1], 1):
            if runner.exhausted():
                return choices
            if visit.kind != kind:
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
            if kind == "FREE":
                runner.counts["budget_free_contact_checks"] += 1
                try:
                    with profiling(runner.profile, "budget_contact_check_seconds"):
                        if trajectories is None:
                            timing = tuple(
                                tuple(
                                    (time, time)
                                    for time in accumulate(durations, initial=0.0)
                                )
                                for durations in current.connection_times
                            )
                            trajectories, _ = runner.evaluator.build_trajectories(
                                solution, timing
                            )
                        start = sum(current.connection_times[agent][: visit_index - 1])
                        end = start + sum(
                            current.connection_times[agent][
                                visit_index - 1 : visit_index + 1
                            ]
                        )
                        preserves = preserves_local_contacts(
                            runner,
                            solution,
                            trajectories,
                            agent,
                            visit_index,
                            start,
                            end,
                        )
                except (MotionError, ValueError):
                    preserves = False
                if not preserves:
                    runner.counts["budget_free_contact_rejections"] += 1
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
    """Drop locally contact-preserving FREE visits first, then TASK visits.

    FREE removals preserve contacts on the edited segment as a local heuristic.
    TASK removals minimize reward lost per second saved. No communication
    propagation is evaluated before the candidate meets the time budgets.
    """
    with profiling(runner.profile, "budget_repair_seconds"):
        current_solution = solution
        current = preview
        dropped: list[str] = []
        free_dropped: list[str] = []
        total_reward_lost = 0.0
        for kind in ("FREE", "TASK"):
            while any(
                completion > budget + runner.config.budget_tolerance
                for completion, budget in zip(
                    current.completion_times, runner.problem.time_budgets
                )
            ):
                if runner.exhausted():
                    break
                choices = _drop_choices(runner, current_solution, current, kind)
                if not choices:
                    break
                _, reward_lost, _, agent, visit_index, candidate, candidate_preview = (
                    min(choices)
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
        "free_removal_policy": "local_contact_preservation",
        "initial_completion_times": list(preview.completion_times),
        "final_completion_times": list(current.completion_times),
        "tasks_dropped": dropped,
        "free_waypoints_dropped": free_dropped,
        "team_reward_lost": total_reward_lost,
        "within_budgets": within_budgets,
    }
    return (current_solution if within_budgets else None), record
