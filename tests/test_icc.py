from dataclasses import replace
import json
import pytest
from topcc.config import Config,Task
from topcc.environment import smoke_problem
from topcc.solution import direct_solution,Solution,Visit,Meeting
from topcc.operators import normalize,neighbors
from topcc.evaluator import Evaluator
from topcc.scheduling import schedule,ScheduleError
from topcc.solver import run_optimization,result_to_dict
from topcc.archive import Archive


def icc(**kwargs):
    return Config(mode='team_kop_icc',max_evaluations=100,max_iterations=4,max_seconds=10,**kwargs)


def meeting_solution(problem):
    base=direct_solution(problem);routes=[]
    for m,r in enumerate(base.routes):
        point=(4.,0.)
        routes.append((replace(r[0],wait=float(m)),Visit(f'meet{m}','FREE',point),r[-1]))
    return Solution(tuple(routes),meetings=(Meeting('meet0','meet1'),))


def test_stopped_rendezvous_and_wait_expenditure():
    p=smoke_problem(2);c=icc();s=meeting_solution(p)
    timing,_=schedule(s.routes,s.meetings,p,c.handshake_time,c.comm_range)
    assert min(timing[0][1][1],timing[1][1][1])-max(timing[0][1][0],timing[1][1][0])>=.5
    evaluated=Evaluator(p,True,c).evaluate(s)
    assert evaluated.evaluation.motion_budget_valid
    assert evaluated.evaluation.visit_times==timing
    assert evaluated.evaluation.completion_times[0]==pytest.approx(evaluated.evaluation.completion_times[1])
    assert evaluated.evaluation.communication is not None


def test_positive_cycle_and_bad_meeting_references():
    p=smoke_problem(2);base=direct_solution(p);routes=[]
    for m,r in enumerate(base.routes):
        routes.append((r[0],Visit(f'{m}a','FREE',(2,0)),Visit(f'{m}b','FREE',(6,0)),r[-1]))
    pairs=(Meeting('0a','1b'),Meeting('0b','1a'))
    with pytest.raises(ScheduleError):schedule(routes,pairs,p,.5,100)
    bad=Solution(tuple(routes),meetings=(Meeting('0a','missing'),))
    assert not Evaluator(p,True,icc()).evaluate(bad).evaluation.valid


def test_malformed_free_budget_and_workspace():
    p=smoke_problem(2);s=meeting_solution(p)
    assert not Evaluator(p,True).evaluate(s).evaluation.valid
    assert not Evaluator(p,True,icc(max_free_waypoints=0)).evaluate(s).evaluation.valid
    assert not Evaluator(p,True,icc(waypoint_workspace=(0,1,0,1))).evaluate(s).evaluation.valid
    assert not Evaluator(replace(p,time_budgets=(1,1)),True,icc()).evaluate(s).evaluation.valid


def test_communication_failure_not_in_archive():
    p=smoke_problem(2);base=direct_solution(p)
    task=p.tasks[0]
    routes=(base.routes[0][:-1]+(Visit('task','TASK',task.position,(0,0),task.id),base.routes[0][-1]),base.routes[1])
    s=Evaluator(p,True,icc(comm_range=.1,recurrence_bound=.01)).evaluate(Solution(routes))
    assert s.evaluation.motion_budget_valid and not s.evaluation.valid and s.evaluation.comm_violation>0
    assert not Archive().add(s)


def test_tc_monotonicity_and_independent_delta():
    p=smoke_problem(2);s=meeting_solution(p);values=[]
    for tc in (.1,1,5,20):
        e=Evaluator(p,True,icc(recurrence_bound=tc)).evaluate(s).evaluation
        values.append((e.peak_staleness,e.valid))
    assert len({d for d,_ in values})==1
    assert [v for _,v in values]==sorted(v for _,v in values)


def test_meeting_identity_survives_order_edits_and_cleanup():
    p=smoke_problem(2);s=meeting_solution(p)
    moved=normalize(s.routes,s.meetings)
    assert moved.meetings==s.meetings and moved.key==s.key
    route=moved.routes[0]
    cleared=normalize((route[:1]+route[2:],moved.routes[1]),moved.meetings)
    assert not cleared.meetings
    renamed=Solution(tuple(tuple(replace(v,id='x'+v.id) for v in r) for r in s.routes),meetings=(Meeting('xmeet0','xmeet1'),))
    assert renamed.key==s.key


def test_all_communication_families_construct_candidates():
    p=smoke_problem(2);c=icc(waypoint_workspace=(-2,10,-5,5));e=Evaluator(p,True,c)
    s=e.evaluate(meeting_solution(p))
    for family in ('wait','meeting','free_move','free_remove'):
        candidates=list(neighbors(s,p,c,family))
        assert candidates, family
        for candidate in candidates[:30]:
            assessed=e.evaluate(candidate)
            assert assessed.evaluation.valid or assessed.evaluation.reason
            assert all(r[0].kind=='START' and r[-1].kind=='END' for r in candidate.routes)


def test_icc_run_and_serializable_bank_reproducibility():
    p=smoke_problem(2);c=icc(comm_range=1,recurrence_bound=2)
    a=run_optimization(p,c);b=run_optimization(p,c)
    assert a.front and all(s.evaluation.comm_violation==0 for s in a.front)
    assert [(s.key,s.objectives) for s in a.front]==[(s.key,s.objectives) for s in b.front]
    data=result_to_dict(a);json.dumps(data,allow_nan=False)
    assert data['schema_version']==2 and data['candidate_bank']
    assert all(len(s['objectives'])==2 and s['communication'] is not None for s in data['front'])


def test_single_agent_icc_delta_zero_and_short_mission():
    p=smoke_problem();r=run_optimization(p,icc(recurrence_bound=.1))
    assert all(s.evaluation.peak_staleness==0 for s in r.front)
    p=smoke_problem(2);direct=Evaluator(p,True,icc(recurrence_bound=100)).evaluate(direct_solution(p))
    assert direct.evaluation.valid


def test_invalid_ids_cannot_hit_valid_evaluation_cache():
    p=smoke_problem();e=Evaluator(p);s=direct_solution(p);assert e.evaluate(s).evaluation.valid
    duplicate=Solution(((s.routes[0][0],replace(s.routes[0][1],id=s.routes[0][0].id)),))
    assert not e.evaluate(duplicate).evaluation.valid


def test_free_meeting_improves_over_task_location_meeting_candidates():
    from topcc.config import Problem,MotionLimits
    p=Problem((Task('a',(2,3),10),Task('b',(6,-3),10)),(0,0),(8,0),(20,20),(MotionLimits(),)*2,((0,0),)*2)
    c=icc(comm_range=1,handshake_time=.25,recurrence_bound=5.05)
    e=Evaluator(p,True,c);base=direct_solution(p);routes=[]
    for m,task in enumerate(p.tasks):
        routes.append((base.routes[m][0],Visit(f'task{m}','TASK',task.position,(0,0),task.id),base.routes[m][-1]))
    original=e.evaluate(Solution(tuple(routes)))
    assert not original.evaluation.valid
    def rendezvous(point,task_id=None):
        rows=[]
        for m,route in enumerate(routes):
            rows.append(route[:-1]+(Visit(f'meet{m}','TASK' if task_id else 'FREE',point,(0,0),task_id),route[-1]))
        return e.evaluate(Solution(tuple(rows),meetings=(Meeting('meet0','meet1'),)))
    free=rendezvous((5,0))
    assert free.evaluation.valid and free.evaluation.reward==20
    # Controlled spatial alternatives with the same stop states and visit order,
    # not a claim that all conceivable task-only routes are infeasible.
    for task in p.tasks:
        limited=rendezvous(task.position,task.id)
        assert not limited.evaluation.valid
        assert free.evaluation.peak_staleness<limited.evaluation.peak_staleness


def test_tiny_deadlock_not_hidden_by_time_tolerance():
    p=smoke_problem(2);base=direct_solution(p)
    rows=[]
    for m,r in enumerate(base.routes):
        rows.append((r[0],Visit(f'{m}a','FREE',(2,0)),Visit(f'{m}b','FREE',(6,0)),r[-1]))
    with pytest.raises(ScheduleError):schedule(rows,(Meeting('0a','1b'),Meeting('0b','1a')),p,1e-12,100)


def test_terminal_contact_does_not_waive_handshake():
    from topcc.communication import evaluate_communication
    from topcc.trajectory import AgentTrajectory,MotionPiece,State
    # Early agent remains at the common destination, last approach enters range
    # .1s before final arrival, too short for the required .5s handshake.
    a=AgentTrajectory((),0,State((0,0)),State((0,0)))
    b=AgentTrajectory((MotionPiece((10,0),(-1,0),(0,0),10,0),),10,State((10,0),(-1,0)),State((0,0)))
    result=evaluate_communication((a,b),.1,.5)
    assert result.contacts[0].raw[0][0]==pytest.approx(9.9)
    assert result.contacts[0].effective==()
    assert result.peak_staleness==10


def test_pool_retains_communication_infeasible_only():
    from topcc.runner import Runner
    p=smoke_problem(2);c=icc(comm_range=.1,recurrence_bound=.01)
    runner=Runner(p,c,allow_team=True)
    from time import perf_counter
    runner.started=perf_counter()
    base=direct_solution(p);task=p.tasks[0]
    routes=(base.routes[0][:-1]+(Visit('task','TASK',task.position,(0,0),task.id),base.routes[0][-1]),base.routes[1])
    assessed=runner.evaluate(Solution(routes),'fixture')
    assert assessed and runner.working_pool and not runner.archive.front
    assert assessed.evaluation.motion_budget_valid and not assessed.evaluation.valid
    disabled=Runner(p,replace(c,working_pool_size=0),allow_team=True);disabled.started=perf_counter()
    assert disabled.evaluate(Solution(routes),'fixture') is None and not disabled.working_pool


def test_root_uncertainty_never_enters_front(monkeypatch):
    import topcc.communication
    from topcc.contacts import ContactUncertain
    def unresolved(*args):raise ContactUncertain('fixture unresolved tangent')
    monkeypatch.setattr(topcc.communication,'evaluate_communication',unresolved)
    p=smoke_problem(2);s=Evaluator(p,True,icc()).evaluate(direct_solution(p))
    assert not s.evaluation.valid and not s.evaluation.motion_budget_valid
    assert s.evaluation.validation_status=='unresolved'
    assert not Archive().add(s)


def test_insertion_never_rebinds_existing_meeting_identity():
    p=smoke_problem(2);c=icc();base=direct_solution(p);task=p.tasks[0]
    rows=[]
    for m,r in enumerate(base.routes):
        rows.append((r[0],Visit(f'task:{m}','TASK',task.position,(0,0),task.id),r[-1]))
    s=Evaluator(p,True,c).evaluate(Solution(tuple(rows),meetings=(Meeting('task:0','task:1'),)))
    assert s.evaluation.motion_budget_valid
    for candidate in list(neighbors(s,p,c,'insert'))[:20]:
        visits={v.id:v for r in candidate.routes for v in r}
        assert visits['task:0'].task_id==task.id and visits['task:1'].task_id==task.id
        assert candidate.meetings==s.meetings
