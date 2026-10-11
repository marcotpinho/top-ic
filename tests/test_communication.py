import numpy as np
import pytest
from topcc.communication import ContactRecord,sweep


def record(m,n,*intervals):
    return ContactRecord((m,n),tuple(intervals),tuple(intervals))


def backwards_clock(num_agents,records,time,left=False):
    # Independent latest-departure oracle: reverse temporal reachability,
    # with each receiver as a deadline root. No forward component sweep.
    links=[(m,n,s,e) for r in records for m,n in [r.agents] for s,e in r.effective if not left or s<time]
    answer=np.zeros((num_agents,num_agents))
    for receiver in range(num_agents):
        latest=np.full(num_agents,-np.inf);latest[receiver]=time
        for _ in range(max(1,len(links)*num_agents+1)):
            changed=False
            for m,n,s,e in links:
                for u,v in ((m,n),(n,m)):
                    t=min(latest[v],e)
                    if t>=s and t>latest[u]:latest[u]=t;changed=True
            if not changed:break
        answer[receiver]=np.maximum(latest,0)
    return answer


def oracle_delta(num_agents,records,T):
    events=sorted(set([0.,T,*[t for r in records for s,e in r.effective for t in (s,e)]]))
    peak=0.
    for time in events:
        for left in (False,True):
            H=backwards_clock(num_agents,records,time,left)
            for n in range(num_agents):
                for m in range(num_agents):
                    if m!=n:peak=max(peak,time-H[n,m])
    return peak


def test_unattained_peak_before_final_exchange():
    r=(record(0,1,(0,1),(5,6)),)
    result=sweep(2,6,r)
    assert result.peak_staleness==4
    assert result.final_clock==((6,6),(6,6))
    assert result.bottleneck[2:]==(5.,'left')


def test_chronological_order_matters():
    forward=(record(0,1,(1,1)),record(1,2,(2,2)))
    reverse=(record(0,1,(2,2)),record(1,2,(1,1)))
    a=sweep(3,3,forward);b=sweep(3,3,reverse)
    assert a.final_clock[2][0]==1
    assert b.final_clock[2][0]==0
    assert a.peak_staleness==oracle_delta(3,forward,3)
    assert b.peak_staleness==oracle_delta(3,reverse,3)


def test_simultaneous_relay_and_edge_order():
    r=(record(0,1,(2,2)),record(1,2,(2,2)))
    a=sweep(3,3,r);b=sweep(3,3,tuple(reversed(r)))
    assert a==sweep(3,3,r)
    assert a.final_clock==b.final_clock
    assert a.final_clock[2][0]==2


def test_end_and_start_at_same_instant():
    r=(record(0,1,(0,2)),record(1,2,(2,4)))
    result=sweep(3,4,r)
    assert result.final_clock[2][0]==2
    assert result.peak_staleness==oracle_delta(3,r,4)


def test_steady_component_and_initial_information():
    assert sweep(3,10,(record(0,1,(0,10)),record(1,2,(0,10)))).peak_staleness==0
    assert sweep(3,10,()).peak_staleness==10
    assert sweep(1,10,()).peak_staleness==0
    assert sweep(2,0,()).peak_staleness==0


def test_random_temporal_schedules_against_backwards_oracle():
    rng=np.random.default_rng(6)
    for _ in range(100):
        records=[]
        for m in range(3):
            for n in range(m+1,3):
                intervals=[]
                for k in range(3):
                    start=float(rng.integers(0,6));end=float(rng.integers(int(start),7))
                    intervals.append((start,end))
                records.append(record(m,n,*intervals))
        result=sweep(3,6,tuple(records))
        assert result.peak_staleness==pytest.approx(oracle_delta(3,records,6))
        assert np.array(result.final_clock)==pytest.approx(backwards_clock(3,records,6))
