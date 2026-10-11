from dataclasses import replace
from itertools import permutations,product
import pytest
from topcc.config import Config,Task,MotionLimits
from topcc.environment import smoke_problem
from topcc.solution import direct_solution,Visit,Solution
from topcc.evaluator import Evaluator
from topcc.archive import Archive
from topcc.operators import normalize,neighbors
from topcc.solver import run_optimization
from topcc.trajectory import Connection,validate_connection


def team_problem():
    return replace(smoke_problem(2),tasks=(Task('a',(2,1),5),Task('b',(5,-1),8)))


def test_single_reduction():
    p=smoke_problem();kw=dict(max_evaluations=200,max_seconds=10,max_iterations=5)
    a=run_optimization(p,Config(**kw));b=run_optimization(p,Config(mode='team_kop',disabled=('assignment',),**kw))
    assert [(s.key,s.objectives) for s in a.front]==[(s.key,s.objectives) for s in b.front]


def test_shared_reward_mean_and_terminal_presence():
    p=team_problem();routes=list(direct_solution(p).routes)
    for m in range(2):
        task=p.tasks[0];routes[m]=(routes[m][0],Visit(f'{m}:task','TASK',task.position,(0,0),task.id),routes[m][-1])
    routes[1]=(replace(routes[1][0],wait=1),*routes[1][1:])
    s=Evaluator(p,allow_team=True).evaluate(Solution(tuple(routes)))
    assert s.evaluation.valid and s.evaluation.reward==5
    c=s.evaluation.completion_times
    assert c[1]-c[0]==pytest.approx(1)
    assert s.objectives[1]==pytest.approx(sum(c)/2)
    assert s.evaluation.trajectories[0].state(c[1]).position==p.end
    assert s.evaluation.trajectories[0].completion_time==c[0]
    assert s.evaluation.first_visitors[0][1]==0


def test_individual_budget_and_empty_agent():
    p=replace(team_problem(),time_budgets=(1,100))
    s=Evaluator(p,allow_team=True).evaluate(direct_solution(p))
    assert not s.evaluation.valid and s.evaluation.completion_times[1]>0


def test_team_tiny_exhaustive_front():
    p=team_problem();oracle=Archive(100);e=Evaluator(p,allow_team=True);base=direct_solution(p)
    for assignment in product((-1,0,1),repeat=2):
        groups=[tuple(t for t,m in zip(p.tasks,assignment) if m==agent) for agent in range(2)]
        for orders in product(*(list(permutations(g)) for g in groups)):
            routes=[]
            for m,order in enumerate(orders):
                visits=tuple(Visit('tmp','TASK',t.position,(0,0),t.id) for t in order)
                routes.append((base.routes[m][0],*visits,base.routes[m][-1]))
            oracle.add(e.evaluate(normalize(routes)))
    r=run_optimization(p,Config(mode='team_kop',headings=2,speed_fractions=(0,),max_evaluations=10000,max_iterations=100,max_seconds=20))
    assert {s.objectives for s in r.front}=={s.objectives for s in oracle.front}
    for s in r.front:
        for m,t in enumerate(s.evaluation.trajectories):
            assert validate_connection(Connection(t.pieces,t.completion_time),t.start,t.end,p.limits[m])


def test_assignment_and_heterogeneous_motion():
    p=replace(team_problem(),limits=(MotionLimits(),MotionLimits((1,1),(.5,.5))),time_budgets=(20,30))
    e=Evaluator(p,allow_team=True);base=direct_solution(p);task=p.tasks[0]
    route=(base.routes[0][0],Visit('task','TASK',task.position,(3,0),task.id),base.routes[0][-1])
    s=e.evaluate(normalize((route,base.routes[1])))
    candidates=list(neighbors(s,p,Config(mode='team_kop',speed_fractions=(0,1)), 'assignment'))
    assert candidates
    valid=[e.evaluate(c) for c in candidates if e.evaluate(c).evaluation.valid]
    assert valid and any(len(c.routes[1])>2 for c in valid)
    for c in valid:
        ids=[v.id for r in c.routes for v in r]
        assert len(ids)==len(set(ids))


def test_identical_permutation_and_crossing_allowed():
    p=team_problem();e=Evaluator(p,allow_team=True);base=direct_solution(p)
    task=p.tasks[0];route=(base.routes[0][0],Visit('task','TASK',task.position,(0,0),task.id),base.routes[0][-1])
    a=e.evaluate(normalize((route,base.routes[1])));b=e.evaluate(normalize((base.routes[1],route)))
    assert a.objectives==b.objectives
    assert e.evaluate(base).evaluation.valid  # Full co-location is deliberately legal.


def test_stage_gates_and_team_run():
    with pytest.raises(ValueError):run_optimization(team_problem(),Config())
    with pytest.raises(ValueError):run_optimization(team_problem(),Config(mode='team_kop_icc',algorithm='lns'))
    with pytest.raises(ValueError):run_optimization(team_problem(),Config(mode='team_kop',algorithm='lns'))
    r=run_optimization(team_problem(),Config(mode='team_kop',max_evaluations=300,max_seconds=10,max_iterations=10))
    assert r.front and all(s.evaluation.valid for s in r.front)
