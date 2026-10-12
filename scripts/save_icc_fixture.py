"""Record a controlled ICC free-waypoint comparison without optimizer starts."""

import json
from dataclasses import asdict
from pathlib import Path

from topcc.config import Config, MotionLimits, Problem, Task
from topcc.environment import problem_to_dict
from topcc.evaluation_core.evaluator import Evaluator
from topcc.solution import Meeting, Solution, Visit, direct_solution
from topcc.solver import solution_to_dict
from topcc.viz_icc import plot_communication

from scripts.validate_icc import validate_solution

ROOT = Path(__file__).resolve().parents[1]


def _variants(problem: Problem, evaluator: Evaluator) -> dict[str, Solution]:
    base = direct_solution(problem)
    routes = [
        (
            base.routes[agent][0],
            Visit(f"task{agent}", "TASK", task.position, task_id=task.id),
            base.routes[agent][-1],
        )
        for agent, task in enumerate(problem.tasks)
    ]
    variants = {"no_meeting": evaluator.evaluate(Solution(tuple(routes)))}
    locations = (
        ("free", (5.0, 0.0), None),
        ("task_a", problem.tasks[0].position, "a"),
        ("task_b", problem.tasks[1].position, "b"),
    )
    for name, position, task_id in locations:
        meeting_routes = tuple(
            route[:-1]
            + (
                Visit(
                    f"meet{agent}",
                    "TASK" if task_id else "FREE",
                    position,
                    task_id=task_id,
                ),
                route[-1],
            )
            for agent, route in enumerate(routes)
        )
        decision = Solution(meeting_routes, meetings=(Meeting("meet0", "meet1"),))
        variants[name] = evaluator.evaluate(decision)
    return variants


def save_fixture(directory: str | Path) -> dict[str, dict]:
    """Write fixed decisions, exact outputs, and independent validation."""
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    problem = Problem(
        (Task("a", (2, 3), 10), Task("b", (6, -3), 10)),
        (0, 0),
        (8, 0),
        (20, 20),
        (MotionLimits(),) * 2,
        ((0, 0),) * 2,
        "controlled-free-rendezvous",
    )
    config = Config(
        comm_range=1,
        handshake_time=0.25,
        recurrence_bound=5.05,
        waypoint_workspace=(-1, 9, -4, 4),
    )
    scored = _variants(problem, Evaluator(problem, config))
    variants = {
        name: json.loads(json.dumps(solution_to_dict(solution)))
        for name, solution in scored.items()
    }
    reference = {
        "schema_version": 4,
        "reward_policy": "explicit_task_visits",
        "problem": problem_to_dict(problem),
        "config": asdict(config),
        "statistics": {},
        "front": [],
    }
    reference = json.loads(json.dumps(reference))
    checks = {
        name: validate_solution(reference, solution, require_feasible=False)
        for name, solution in variants.items()
    }
    assert variants["free"]["comm_violation"] == 0
    assert all(
        variants[name]["comm_violation"] > 0
        for name in ("no_meeting", "task_a", "task_b")
    )
    record = {
        **reference,
        "method": "fixed states/order/assignment, spatial alternatives only",
        "variants": variants,
        "validation": checks,
    }
    output = destination / "controlled-free-fixture.json"
    output.write_text(json.dumps(record, indent=2) + "\n")
    plot_communication(
        {**reference, "front": [variants["free"]]},
        destination,
        prefix="controlled-free",
    )
    return variants


if __name__ == "__main__":
    save_fixture(ROOT / "results/step4")
