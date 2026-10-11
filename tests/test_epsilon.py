from dataclasses import replace
import pytest
from topcc.archive import Archive
from topcc.config import Config
from topcc.environment import smoke_problem
from topcc.evaluator import Evaluator
from topcc.solution import direct_solution


def scored(objectives):
    s=Evaluator(smoke_problem()).evaluate(direct_solution(smoke_problem()))
    return replace(s,routes=((replace(s.routes[0][0],wait=abs(objectives[0])+objectives[1]),)+s.routes[0][1:],),evaluation=replace(s.evaluation,objectives=objectives))


def test_epsilon_same_box_representative_and_negative_floor():
    a=Archive(20,5,1)
    bad=scored((-6,2.8));good=scored((-9,2.1))
    assert a.box(bad)==(-2,2)
    assert a.add(bad) and a.add(good)
    assert a.front==[good]
    assert not a.add(bad)


def test_epsilon_dominance_not_crowding():
    a=Archive(20,5,1)
    a.add(scored((-9,3.1)))
    assert not a.add(scored((-6,3.8)))
    assert a.add(scored((-5,2.1)))
    assert len(a.front)==2
    assert all(not a.box_dominates(a.box(x),a.box(y)) for x in a.front for y in a.front)


def test_capacity_uses_epsilon_coarsening():
    a=Archive(2,.1,.1)
    for i in range(8):a.add(scored((-i,1+i)))
    assert len(a.front)<=2 and a.coarsenings>0
    assert a.epsilon[0]>.1


def test_invalid_epsilon():
    with pytest.raises(ValueError):Config(eps_time=0)
    with pytest.raises(ValueError):Archive(eps_reward=float('nan'))
