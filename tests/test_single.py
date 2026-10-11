from dataclasses import replace
from itertools import permutations,product
import pytest
from topcc.config import Config,Task,velocity_menu
from topcc.environment import smoke_problem
from topcc.solution import Solution,Visit,direct_solution
from topcc.evaluator import Evaluator
from topcc.archive import Archive
from topcc.solver import run_optimization,result_to_dict
from topcc.operators import normalize,neighbors,SINGLE_NEIGHBORHOODS
from topcc.trajectory import Connection,validate_connection


def small_problem():
    return replace(smoke_problem(),tasks=(Task("a",(2,1),5),Task("b",(5,-1),8)))


def test_dominance_equality():
    evaluator=Evaluator(small_problem());s=evaluator.evaluate(direct_solution(small_problem()))
    assert not s.dominates(s)
    archive=Archive();assert archive.add(s);assert not archive.add(s)


def test_tiny_exhaustive_front():
    p=small_problem();config=Config(max_evaluations=10000,max_iterations=100,max_seconds=20,headings=2,speed_fractions=(0,))
    evaluator=Evaluator(p);oracle=Archive(100)
    direct=direct_solution(p).routes[0]
    for k in range(3):
        for selected in permutations(p.tasks,k):
            visits=tuple(Visit(str(i),"TASK",t.position,(0,0),t.id) for i,t in enumerate(selected))
            oracle.add(evaluator.evaluate(normalize(((direct[0],*visits,direct[-1]),))))
    result=run_optimization(p,config)
    assert {s.objectives for s in result.front}=={s.objectives for s in oracle.front}
    for s in result.front:
        t=s.evaluation.trajectories[0]
        assert validate_connection(Connection(t.pieces,t.completion_time),t.start,t.end,p.limits[0])


def test_reproducibility_and_json():
    p=small_problem();c=Config(max_evaluations=150,max_iterations=5,max_seconds=10)
    a=run_optimization(p,c);b=run_optimization(p,c)
    assert [(s.key,s.objectives) for s in a.front]==[(s.key,s.objectives) for s in b.front]
    import json
    json.dumps(result_to_dict(a),allow_nan=False)
    assert len(a.front)>1


def test_neighborhood_disable_and_failure():
    p=small_problem();r=run_optimization(p,Config(disabled=("insert",),max_evaluations=100))
    assert len(r.front)==1 and len(r.front[0].routes[0])==2
    tight=replace(p,time_budgets=(.1,))
    r=run_optimization(tight,Config())
    assert r.status=="no_known_feasible_seed" and not r.front
    with pytest.raises(ValueError):run_optimization(p,Config(disabled=("wrong",)))


def test_all_neighbor_family_invariants():
    p=small_problem();config=Config(max_evaluations=300,max_seconds=10)
    result=run_optimization(p,config);e=Evaluator(p)
    for family in SINGLE_NEIGHBORHOODS:
        for s in result.front:
            for candidate in neighbors(s,p,config,family):
                assessed=e.evaluate(candidate)
                assert len(candidate.routes)==1
                assert candidate.routes[0][0].kind=="START" and candidate.routes[0][-1].kind=="END"
                if assessed.evaluation.valid:
                    assert assessed.evaluation.completion_times[0]<=p.time_budgets[0]+1e-7


def test_lns_baseline_bounded():
    p=small_problem();r=run_optimization(p,Config(algorithm="lns",max_evaluations=150,max_seconds=10,max_iterations=5))
    assert r.front and r.statistics["evaluated"]<=150
