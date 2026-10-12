"""One exact regression gate for each evaluator pipeline stage."""

import json
from dataclasses import asdict
from pathlib import Path

from src.config import Config
from src.entities.evaluator import Evaluator
from src.environment import problem_from_dict
from src.solution import Meeting, Solution, Visit
from tests.reference_helpers import json_value

REFERENCE = json.loads(
    (Path(__file__).parent / "data" / "evaluator_reference.json").read_text()
)


def _case():
    case = next(
        item for item in REFERENCE if item["name"] == "relay_feasible_free_waypoint"
    )
    problem = problem_from_dict(case["problem"])
    config = Config(**case["config"])
    solution = Solution(
        tuple(tuple(Visit(**visit) for visit in route) for route in case["routes"]),
        meetings=tuple(Meeting(**meeting) for meeting in case["meetings"]),
    )
    return case, solution, Evaluator(problem, config)


def test_structure_stage():
    _, solution, evaluator = _case()
    assert evaluator.validate_structure(solution) is None


def test_scheduling_stage():
    case, solution, evaluator = _case()
    assert (
        json_value(evaluator.schedule_solution(solution))
        == case["expected"]["visit_times"]
    )


def test_trajectory_stage():
    case, solution, evaluator = _case()
    timing = evaluator.schedule_solution(solution)
    trajectories, visit_times = evaluator.build_trajectories(solution, timing)
    assert (
        json_value([asdict(item) for item in trajectories])
        == case["expected"]["trajectories"]
    )
    assert json_value(visit_times) == case["expected"]["visit_times"]


def test_reward_stage():
    case, solution, evaluator = _case()
    _, visit_times = evaluator.build_trajectories(
        solution, evaluator.schedule_solution(solution)
    )
    reached, owners, reward = evaluator.credit_rewards(solution, visit_times)
    assert json_value(reached) == case["expected"]["reached_tasks"]
    assert reward == -case["expected"]["objectives"][0]
    assert (
        json_value(
            tuple((task, agent, time) for task, (time, agent) in sorted(owners.items()))
        )
        == case["expected"]["first_visitors"]
    )


def test_budget_stage():
    case, _, evaluator = _case()
    assert evaluator.check_budgets(tuple(case["expected"]["completion_times"]))


def test_communication_stage():
    case, solution, evaluator = _case()
    trajectories, _ = evaluator.build_trajectories(
        solution, evaluator.schedule_solution(solution)
    )
    communication, violation = evaluator.evaluate_links(trajectories, True)
    assert json_value(asdict(communication)) == case["expected"]["communication"]
    assert violation == case["expected"]["comm_violation"]


def test_objective_assembly_stage():
    case, solution, evaluator = _case()
    trajectories, visit_times = evaluator.build_trajectories(
        solution, evaluator.schedule_solution(solution)
    )
    reached, owners, reward = evaluator.credit_rewards(solution, visit_times)
    completion_times = tuple(trajectory.completion_time for trajectory in trajectories)
    communication, violation = evaluator.evaluate_links(trajectories, True)
    result = evaluator.assemble_objectives(
        True,
        completion_times,
        reached,
        trajectories,
        visit_times,
        owners,
        reward,
        communication,
        violation,
    )
    assert json_value(asdict(result)) == case["expected"]
