"""Small exhaustive relay benchmark and deterministic rebuilt-search gates."""

from itertools import permutations, product
from random import Random
from types import SimpleNamespace

import pytest

from src.config import Config, MotionLimits, Problem, Task
from src.entities.archive import Archive
from src.entities.evaluator import Evaluator
from src.entities.neighborhood import Neighborhood
from src.entities.profiling import SearchProfile
from src.entities.runner import Runner
from src.entities.search_loop import _search_family
from src.evaluation_core.trajectory import MotionError, State, connect
from src.solution import Solution, Visit, direct_solution
from src.solver import result_to_dict


def relay_problem():
    return Problem(
        (Task("a", (-2.0, 0.0), 5.0), Task("b", (2.0, 0.0), 7.0)),
        (0.0, 0.0),
        (0.0, 0.0),
        (6.5, 6.5),
        (MotionLimits(), MotionLimits()),
        ((0.0, 0.0), (0.0, 0.0)),
        "two-task-relay",
    )


def route_orders():
    return ((), ("a",), ("b",), *permutations(("a", "b")))


def fixed_solution(problem, orders):
    return Solution(
        tuple(
            (
                Visit(f"{agent}:start", "START", problem.start),
                *(
                    Visit(
                        f"{agent}:{task}",
                        "TASK",
                        problem.task_map[task].position,
                        task_id=task,
                    )
                    for task in order
                ),
                Visit(f"{agent}:end", "END", problem.end),
            )
            for agent, order in enumerate(orders)
        )
    )


def settings(tc, seed=1):
    return Config(
        seed=seed,
        comm_range=0.5,
        handshake_time=0.2,
        recurrence_bound=tc,
        max_seconds=3.0,
        max_evaluations=200,
        max_iterations=6,
    )


def brute_force_best(problem, config):
    """Exhaust all 25 task-order pairs in the declared finite relay space."""
    evaluator = Evaluator(problem, config)
    feasible = []
    for orders in product(route_orders(), repeat=2):
        scored = evaluator.evaluate(fixed_solution(problem, orders))
        if scored.evaluation.valid and scored.objectives[2] == 0:
            feasible.append(scored)
    return max(solution.evaluation.reward for solution in feasible)


@pytest.mark.parametrize("tc,expected", ((0.5, 7.0), (2.0, 7.0), (10.0, 12.0)))
@pytest.mark.parametrize("seed", (1, 2, 3))
def test_relay_search_matches_brute_force(tc, expected, seed):
    problem = relay_problem()
    config = settings(tc, seed)
    assert brute_force_best(problem, config) == expected
    result = Runner(problem, config).run()
    assert result.status == "ok"
    feasible = [solution for solution in result.front if solution.objectives[2] == 0]
    assert max(solution.evaluation.reward for solution in feasible) == expected


def test_infinite_tc_agrees_with_team_kop():
    problem = relay_problem()
    orders = (("a",), ("b",))
    solution = fixed_solution(problem, orders)
    team = team_kop_objectives(problem, solution)
    icc = Evaluator(problem, settings(1e9)).evaluate(solution)
    assert team == icc.objectives[:2]
    assert icc.objectives[2] == 0
    for seed in (1, 2, 3):
        team_best = max(
            -objectives[0]
            for orders in product(route_orders(), repeat=2)
            if (
                objectives := team_kop_objectives(
                    problem, fixed_solution(problem, orders)
                )
            )
            is not None
        )
        icc_result = Runner(problem, settings(1e9, seed)).run()
        assert team_best == max(
            solution.evaluation.reward
            for solution in icc_result.front
            if solution.objectives[2] == 0
        )


def team_kop_objectives(problem, solution):
    """Independently score eqs. (5), (7), (8) without communication."""
    completion_times = []
    for agent, route in enumerate(solution.routes):
        try:
            completion = sum(
                connect(
                    State(start.position, start.velocity),
                    State(end.position, end.velocity),
                    problem.limits[agent],
                ).duration
                for start, end in zip(route, route[1:])
            )
        except MotionError:
            return None
        if completion > problem.time_budgets[agent] + 1e-7:
            return None
        completion_times.append(completion)
    visited = {
        visit.task_id
        for route in solution.routes
        for visit in route
        if visit.kind == "TASK"
    }
    reward = sum(task.reward for task in problem.tasks if task.id in visited)
    return -reward, sum(completion_times) / len(completion_times)


def test_fixed_seed_repeats_front():
    problem = relay_problem()
    config = settings(2.0, seed=19)
    first = Runner(problem, config).run()
    second = Runner(problem, config).run()
    assert [(solution.key, solution.objectives) for solution in first.front] == [
        (solution.key, solution.objectives) for solution in second.front
    ]


def test_search_profiling_is_saved_by_family():
    result = Runner(relay_problem(), settings(2.0, seed=19)).run()
    profile = result_to_dict(result)["statistics"]["profiling"]
    assert profile["search_loop_seconds"] > 0
    assert profile["evaluation_seconds"] >= profile["evaluator_seconds"] > 0
    assert set(profile["neighborhoods"]) == set(Neighborhood.ICC)
    assert any(row["calls"] for row in profile["neighborhoods"].values())
    for row in profile["neighborhoods"].values():
        assert row["total_seconds"] >= row["generation_seconds"] >= 0
        assert row["total_seconds"] >= row["evaluation_seconds"] >= 0
        assert row["total_seconds"] >= row["shake_seconds"] >= 0


def test_shaken_solution_generates_neighbors_before_evaluation(monkeypatch):
    problem = relay_problem()
    base = direct_solution(problem)
    shaken = fixed_solution(problem, (("a",), ()))
    events = []

    class RecordingNeighborhood:
        def generate(self, name, solution):
            events.append(("generation_started", solution))
            yield solution
            events.append(("generation_finished", solution))

    def evaluate(solution, family):
        events.append(("evaluated", family, solution))
        return None

    monkeypatch.setattr(
        "src.entities.search_loop.ruin_recreate", lambda *arguments: shaken
    )
    runner = SimpleNamespace(
        config=settings(2.0),
        rng=Random(1),
        neighborhood=RecordingNeighborhood(),
        profile=SearchProfile.for_neighborhoods(("insert",)),
        evaluate=evaluate,
        exhausted=lambda: False,
    )
    _search_family(runner, "insert", base, 0)
    assert events == [
        ("generation_started", shaken),
        ("generation_finished", shaken),
        ("evaluated", "ruin_recreate", shaken),
        ("evaluated", "insert", shaken),
    ]


def test_archive_keeps_zero_violation_in_own_layer():
    archive = Archive(settings(2.0), Random(4))

    class Point:
        def __init__(self, key, objectives):
            self.key = key
            self.objectives = objectives
            self.evaluation = type("Evaluation", (), {"valid": True})()

    zero = Point("zero", (-5.0, 4.0, 0.0))
    positive = Point("positive", (-6.0, 4.0, 0.01))
    assert archive.epsilon.box(zero)[-1] == 0
    assert archive.epsilon.box(positive)[-1] >= 1
    assert archive.add(zero)
    assert archive.add(positive)
    assert {point.key for point in archive.front} == {"zero", "positive"}
