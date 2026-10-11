import importlib.util,json
from pathlib import Path
from dataclasses import replace
import pytest
from topcc.environment import smoke_problem
from topcc.config import Config
from topcc.solver import run_optimization,result_to_dict
from topcc.solution import Solution,Visit,Meeting,direct_solution
from topcc.evaluator import Evaluator

spec=importlib.util.spec_from_file_location('icc_validator',Path(__file__).parents[1]/'scripts/validate_icc.py')
validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)


def test_independent_saved_icc_front_and_bank():
    r=run_optimization(smoke_problem(2),Config(mode='team_kop_icc',max_evaluations=100,max_iterations=4,max_seconds=10))
    data=json.loads(json.dumps(result_to_dict(r)))
    checks=validator.validate(data,True)
    assert checks['solutions_checked']>=len(r.front)>0
    assert checks['max_motion_residual']<2e-6


def test_independent_free_meeting_and_tampering():
    p=smoke_problem(2);c=Config(mode='team_kop_icc',waypoint_workspace=(-2,10,-4,4),recurrence_bound=10)
    rows=[]
    for m,r in enumerate(direct_solution(p).routes):
        rows.append((r[0],Visit(f'f{m}','FREE',(4,0)),r[-1]))
    s=Evaluator(p,True,c).evaluate(Solution(tuple(rows),meetings=(Meeting('f0','f1'),)))
    from topcc.runner import RunResult
    data=json.loads(json.dumps(result_to_dict(RunResult(p,c,[s],{},0,'fixture'))))
    assert validator.validate(data)['front_size']==1
    data['front'][0]['peak_staleness']+=1
    with pytest.raises(AssertionError):validator.validate(data)


def test_existing_team_benchmark_paths_revalidated_with_communication():
    from topcc.environment import problem_from_dict
    from topcc.solver import solution_to_dict
    path=Path(__file__).parents[1]/'experiments/team/full.json'
    saved=json.loads(path.read_text());p=problem_from_dict(saved['problem'])
    c=Config(mode='team_kop_icc',comm_range=2,handshake_time=.5,recurrence_bound=100,waypoint_workspace=(0,20,0,25))
    e=Evaluator(p,True,c)
    for old in saved['front']:
        s=Solution(tuple(tuple(Visit(**v) for v in r) for r in old['routes']))
        out=e.evaluate(s)
        assert out.evaluation.valid
        from topcc.environment import problem_to_dict
        from dataclasses import asdict
        data={'schema_version':2,'problem':problem_to_dict(p),'config':asdict(c),'statistics':{},'front':[solution_to_dict(out)]}
        data=json.loads(json.dumps(data))
        assert validator.validate(data)['front_size']==1
