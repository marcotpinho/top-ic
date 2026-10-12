"""Exact evaluator regression against the frozen pre-rebuild code."""

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from src.config import Config
from src.environment import problem_from_dict
from src.evaluation_core.evaluator import Evaluator as PortedEvaluator
from src.solution import Meeting, Solution, Visit
from tests.reference_helpers import json_value

REFERENCE = json.loads(
    (Path(__file__).parent / "data" / "evaluator_reference.json").read_text()
)


@pytest.mark.parametrize(
    "case",
    [case for case in REFERENCE if case["config"]["mode"] == "team_kop_icc"],
    ids=lambda case: case["name"],
)
def test_evaluator_reference(case):
    problem = problem_from_dict(case["problem"])
    config = Config(**case["config"])
    solution = Solution(
        tuple(tuple(Visit(**visit) for visit in route) for route in case["routes"]),
        meetings=tuple(Meeting(**meeting) for meeting in case["meetings"]),
    )
    evaluated = PortedEvaluator(problem, config).evaluate(solution)
    assert json_value(asdict(evaluated.evaluation)) == case["expected"]
