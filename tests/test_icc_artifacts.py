import json,importlib.util
from pathlib import Path
from topcc.config import Config
from topcc.environment import problem_from_dict
from topcc.solution import Solution,Visit,Meeting
from topcc.evaluator import Evaluator

ROOT=Path(__file__).parents[1]
spec=importlib.util.spec_from_file_location('final_icc_validator',ROOT/'scripts/validate_icc.py')
validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)


def test_saved_near_simultaneous_first_visitor_regression():
    data=json.loads((ROOT/'experiments/icc/task-only-seed7.json').read_text())
    solution=data['candidate_bank'][67]
    checks=validator.validate_solution(data,solution,False)
    assert checks['max_residual']<2e-6


def test_schema_two_can_reconstruct_and_reevaluate_full_solution():
    data=json.loads((ROOT/'experiments/icc/tc5-seed42.json').read_text())
    problem=problem_from_dict(data['problem']);config=Config(**data['config'])
    old=max(data['front'],key=lambda s:s['reward'])
    solution=Solution(tuple(tuple(Visit(**v) for v in r) for r in old['routes']),meetings=tuple(Meeting(**m) for m in old['meetings']))
    result=Evaluator(problem,True,config).evaluate(solution)
    assert result.evaluation.valid
    assert result.objectives==tuple(old['objectives'])
    assert abs(result.evaluation.peak_staleness-old['peak_staleness'])<2e-7


def test_parsed_configuration_copies_mutable_json_arrays():
    steps=[1.,.25];workspace=[0.,10.,-2.,4.]
    config=Config(mode='team_kop_icc',waypoint_steps=steps,wait_steps=[.25,1.],waypoint_workspace=workspace,disabled=[])
    steps.append(100.);workspace[0]=-100.
    assert config.waypoint_steps==(1.,.25)
    assert config.waypoint_workspace==(0.,10.,-2.,4.)
    assert isinstance(config.disabled,tuple)
