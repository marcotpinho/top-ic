from dataclasses import replace
import numpy as np
import pytest
from topcc.contacts import range_intervals,merge_intervals,effective_intervals,pair_contacts,ContactUncertain
from topcc.trajectory import State,AgentTrajectory,MotionPiece


@pytest.mark.parametrize('position,expected',[((0,0),((0.,2.),)),((1,0),((0.,2.),)),((2,0),())])
def test_stationary_range(position,expected):
    assert range_intervals(position,(0,0),(0,0),2,1)==expected


def test_crossing_and_quadratic_reduction():
    result=range_intervals((-2,0),(1,0),(0,0),4,1)
    assert np.asarray(result)==pytest.approx(np.array([[1,3]]))


def test_isolated_tangent_and_near_tangent_uncertainty():
    result=range_intervals((-1,1),(1,0),(0,0),2,1)
    assert result==((1.,1.),)
    with pytest.raises(ContactUncertain):range_intervals((-1,1+1e-13),(1,0),(0,0),2,1)


def test_quartic_two_contacts():
    # Relative x=t²-4t+3: contacts near roots1 and3, with a genuine gap.
    intervals=range_intervals((3,0),(-4,0),(2,0),4,.2)
    assert len(intervals)==2 and intervals[0][1]<intervals[1][0]
    for s,e in intervals:
        assert abs((s*s-4*s+3))==pytest.approx(.2,abs=1e-9)
        assert abs((e*e-4*e+3))==pytest.approx(.2,abs=1e-9)


def test_handshake_boundaries_and_initial_exception():
    assert effective_intervals(((0,.1),),1)==((0,.1),)
    assert effective_intervals(((1,2),),1)==((2,2),)
    assert effective_intervals(((1,1.999999),),1)==()
    assert effective_intervals(((1,2.000001),),1)==((2,2.000001),)
    assert effective_intervals(((2,2),),0)==((2,2),)
    assert effective_intervals(((1,1.6),(1.7,2.3)),1)==()


def test_merge_does_not_bridge_tiny_gap():
    assert merge_intervals(((0,1),(1,2)))==((0.,2.),)
    assert len(merge_intervals(((0,1),(1+1e-12,2))))==2


def test_piece_boundary_merge_and_terminal_extension():
    moving=AgentTrajectory((MotionPiece((0,0),(1,0),(0,0),1,0),MotionPiece((1,0),(1,0),(0,0),1,1)),2,State((0,0),(1,0)),State((2,0)))
    early=AgentTrajectory((MotionPiece((0,0),(2,0),(0,0),1,0),),1,State((0,0),(2,0)),State((2,0)))
    assert pair_contacts(moving,early,2,1)==((0.,2.),)
    assert early.completion_time==1


def test_random_polynomial_interval_classification():
    rng=np.random.default_rng(19)
    for _ in range(80):
        p=rng.uniform(-3,3,2);v=rng.uniform(-3,3,2);a=rng.uniform(-2,2,2);duration=2.
        intervals=range_intervals(p,v,a,duration,1.)
        for t in rng.uniform(0,2,100):
            separation=np.linalg.norm(p+v*t+.5*a*t*t)
            if abs(separation-1)<1e-6:continue
            assert any(s<=t<=e for s,e in intervals)==(separation<1)


def test_zero_horizon_and_constant_polynomial():
    t=AgentTrajectory((),0,State((0,0)),State((0,0)))
    assert pair_contacts(t,t,0,1)==((0.,0.),)
    assert range_intervals((0,0),(0,0),(0,0),1e-6,1)==((0.,1e-6),)
