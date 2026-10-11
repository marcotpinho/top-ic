import json
from dataclasses import replace
import numpy as np
import pytest
from scipy.optimize import linprog
from topcc.config import MotionLimits, Problem, Task
from topcc.environment import smoke_problem, problem_to_dict, problem_from_dict
from topcc.trajectory import State, connect, validate_connection, _bounds
from topcc.solution import direct_solution, Visit, Solution
from topcc.evaluator import Evaluator


def test_schema_and_units():
    p=smoke_problem()
    assert problem_from_dict(json.loads(json.dumps(problem_to_dict(p))))==p
    d=problem_to_dict(p); d["budget_unit"]="distance"
    with pytest.raises(ValueError): problem_from_dict(d)
    with pytest.raises(ValueError): MotionLimits((0,3),(1,1))


@pytest.mark.parametrize("distance,expected",[(1,2),(9,6),(12,7)])
def test_rest_to_rest_analytic(distance,expected):
    lim=MotionLimits((3,3),(1,1))
    c=connect(State((0,0)),State((distance,0)),lim)
    assert c.duration==pytest.approx(expected)
    assert validate_connection(c,State((0,0)),State((distance,0)),lim)


def test_random_motion_and_repeatability():
    rng=np.random.default_rng(4); lim=MotionLimits()
    for _ in range(80):
        s=State(tuple(rng.uniform(-4,4,2)),tuple(rng.uniform(-3,3,2)))
        e=State(tuple(rng.uniform(-4,4,2)),tuple(rng.uniform(-3,3,2)))
        c=connect(s,e,lim)
        assert c==connect(s,e,lim)
        assert validate_connection(c,s,e,lim)
        if c.duration>1e-5:
            # Independent necessary feasibility of both axes at shorter duration.
            t=c.duration-1e-5
            assert any(t<abs(e.velocity[d]-s.velocity[d])/lim.acceleration[d] or not (_bounds(t,s.velocity[d],e.velocity[d],lim.velocity[d],lim.acceleration[d])[0]-1e-9<=e.position[d]-s.position[d]<=_bounds(t,s.velocity[d],e.velocity[d],lim.velocity[d],lim.acceleration[d])[1]+1e-9) for d in range(2))


def test_independent_discrete_control_reference():
    # LP over sampled velocities, independent of connector profile enumeration.
    lim=MotionLimits((3,3),(1,1)); s=State((0,0),(1,0)); e=State((2,1),(-.5,0))
    c=connect(s,e,lim)
    for factor,expect in [(0.97,False),(1.03,True)]:
        T=c.duration*factor; n=300; dt=T/n
        for d in range(2):
            A=[]; b=[]
            for k in range(n):
                row=np.zeros(n+1);row[k+1]=1;row[k]=-1
                A.extend([row,-row]);b.extend([dt,dt])
            weights=np.full(n+1,dt);weights[[0,-1]]=dt/2
            bounds=[(-3,3)]*(n+1);bounds[0]=(s.velocity[d],)*2;bounds[-1]=(e.velocity[d],)*2
            lp=linprog(np.zeros(n+1),A_ub=A,b_ub=b,A_eq=[weights],b_eq=[e.position[d]-s.position[d]],bounds=bounds,method="highs")
            if expect: assert lp.success
            elif d==0: assert not lp.success


def test_wait_budget_and_incidental_passage():
    p=smoke_problem(); p=replace(p,tasks=(Task("cross",(4,0),7),))
    s=direct_solution(p); out=Evaluator(p).evaluate(s)
    assert out.evaluation.reward==7
    route=(replace(s.routes[0][0],wait=2),s.routes[0][1])
    waited=Evaluator(p).evaluate(Solution((route,)))
    assert waited.evaluation.completion_times[0]==pytest.approx(out.evaluation.completion_times[0]+2)
    with pytest.raises(ValueError): Visit("bad","TASK",(1,1),(1,0),"x",1)
    tight=replace(p,time_budgets=(1,))
    assert not Evaluator(tight).evaluate(s).evaluation.valid


def test_coincident_depots_and_zero_duration():
    p=replace(smoke_problem(),start=(0,0),end=(0,0))
    s=Evaluator(p).evaluate(direct_solution(p))
    assert s.evaluation.valid and s.evaluation.completion_times==(0,)
