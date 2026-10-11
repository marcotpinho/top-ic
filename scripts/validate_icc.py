"""Independent motion, quartic-root, and reverse-reachability validation."""
import json,math
from pathlib import Path
import numpy as np

def validate_motion(data):
    problem=data['problem']; tolerance=2e-6; maximum=0.;count=0
    def residual(a,b):
        nonlocal maximum
        r=max(abs(x-y) for x,y in zip(a,b));maximum=max(maximum,r);assert r<tolerance,(a,b,r)
    for solution in data['front']:
        reached=[]; arrivals=[]
        occurrence_ids=[v['id'] for route in solution['routes'] for v in route]
        assert len(occurrence_ids)==len(set(occurrence_ids))
        for m,trajectory in enumerate(solution['trajectories']):
            route=solution['routes'][m]
            assert route[0]['kind']=='START' and route[-1]['kind']=='END'
            assert route[0]['position']==problem['start'] and route[-1]['position']==problem['end']
            assert route[-1]['velocity']==[0.,0.] and route[-1]['wait']==0
            agent=problem['agents'][m];position=np.array(problem['start']);velocity=np.array(agent['initial_velocity']);elapsed=0.;visits={}
            for piece in trajectory['pieces']:
                count+=1;h=piece['duration'];assert h>0
                residual(position,piece['position']);residual(velocity,piece['velocity']);residual([elapsed],[piece['start_time']])
                acceleration=np.array(piece['acceleration']);tail_v=velocity+acceleration*h
                assert np.all(np.abs(acceleration)<=np.array(agent['acceleration_axis_limit'])+tolerance)
                assert np.all(np.maximum(np.abs(velocity),np.abs(tail_v))<=np.array(agent['velocity_axis_limit'])+tolerance)
                for task in problem['tasks']:
                    target=np.array(task['position']);diff=position-target
                    axis=int(np.argmax(np.abs(diff)+np.abs(velocity)+np.abs(acceleration)))
                    coefficients=np.trim_zeros(np.array([.5*acceleration[axis],velocity[axis],diff[axis]]),'f')
                    roots=np.roots(coefficients) if len(coefficients)>1 else []
                    candidates=[0.,h]+[float(r.real) for r in roots if abs(r.imag)<1e-7]
                    for t in candidates:
                        if -1e-8<=t<=h+1e-8 and max(abs(position+velocity*t+.5*acceleration*t*t-target))<tolerance:
                            visits[task['id']]=min(visits.get(task['id'],math.inf),elapsed+max(0.,t))
                position=position+velocity*h+.5*acceleration*h*h;velocity=tail_v;elapsed+=h
            residual(position,problem['end']);residual(velocity,[0,0]);residual([elapsed],[trajectory['completion_time']]);residual([elapsed],[solution['completion_times'][m]])
            assert elapsed<=agent['time_budget']+tolerance
            for task in problem['tasks']:
                if max(abs(np.array(problem['start'])-task['position']))<tolerance:visits[task['id']]=0.
                if max(abs(position-task['position']))<tolerance:visits[task['id']]=min(visits.get(task['id'],math.inf),elapsed)
            assert set(visits)==set(solution['reached_tasks'][m])
            for visit in route[1:-1]:
                assert visit['kind'] in ('TASK','FREE')
                if visit['kind']=='TASK':
                    assert visit['task_id'] in visits
                    task=next(t for t in problem['tasks'] if t['id']==visit['task_id'])
                    assert visit['position']==task['position']
                else:
                    assert visit['task_id'] is None
                    bounds=data['config']['waypoint_workspace']
                    if bounds: assert bounds[0]<=visit['position'][0]<=bounds[1] and bounds[2]<=visit['position'][1]<=bounds[3]
                assert visit['wait']>=0
                if visit['wait']>0:assert visit['velocity']==[0.,0.]
            reached.append(visits);arrivals.append(elapsed)
        union=set().union(*(set(v) for v in reached));reward=sum(t['reward'] for t in problem['tasks'] if t['id'] in union)
        residual([reward,-reward,sum(arrivals)/len(arrivals)],[solution['reward'],*solution['objectives']])
        owners={task:min((v[task],m) for m,v in enumerate(reached) if task in v) for task in union}
        assert set(owners)=={x[0] for x in solution['first_visitors']}
        for task,m,t in solution['first_visitors']:assert owners[task][1]==m;residual([owners[task][0]],[t])
    for i,a in enumerate(data['front']):
        for j,b in enumerate(data['front']):
            if i!=j:assert not(all(x<=y for x,y in zip(a['objectives'],b['objectives'])) and any(x<y for x,y in zip(a['objectives'],b['objectives'])))
    if 'effective_epsilon' in data.get('statistics',{}):
        eps=data['statistics']['effective_epsilon']
        boxes=[tuple(math.floor(f/e) for f,e in zip(s['objectives'],eps)) for s in data['front']]
        assert len(boxes)==len(set(boxes))
        for i,a in enumerate(boxes):
            for j,b in enumerate(boxes):
                if i!=j:assert not(all(x<=y for x,y in zip(a,b)) and any(x<y for x,y in zip(a,b)))
    return {'solutions_checked' :len(data['front']),'motion_pieces_checked':count,'max_residual':maximum,'tolerance':tolerance}


def state_at(trajectory,time):
    if time>=trajectory['completion_time']:
        return np.array(trajectory['end']['position']),np.array(trajectory['end']['velocity'])
    for piece in trajectory['pieces']:
        if piece['start_time']<=time<=piece['start_time']+piece['duration']+1e-10:
            t=max(0.,min(piece['duration'],time-piece['start_time']))
            p=np.array(piece['position']);v=np.array(piece['velocity']);a=np.array(piece['acceleration'])
            return p+v*t+.5*a*t*t,v+a*t
    return np.array(trajectory['start']['position']),np.array(trajectory['start']['velocity'])


def independent_contacts(first,second,T,R):
    def extended(trajectory):
        pieces=list(trajectory['pieces'])
        if trajectory['completion_time']<T:
            pieces.append(dict(position=trajectory['end']['position'],velocity=[0,0],acceleration=[0,0],start_time=trajectory['completion_time'],duration=T-trajectory['completion_time']))
        return pieces
    if T==0:return [(0.,0.)]
    raw=[]
    for a in extended(first):
        for b in extended(second):
            start=max(a['start_time'],b['start_time']);end=min(a['start_time']+a['duration'],b['start_time']+b['duration'])
            if end<start:continue
            pa,va=state_at_piece(a,start);pb,vb=state_at_piece(b,start)
            acc=np.array(a['acceleration'])-np.array(b['acceleration']);q=[np.array([pa[d]-pb[d],va[d]-vb[d],.5*acc[d]]) for d in range(2)]
            coefficients=sum((np.convolve(x,x) for x in q),np.zeros(5));coefficients[0]-=R*R
            poly=np.polynomial.Polynomial(coefficients);duration=end-start
            roots=[float(r.real) for r in poly.roots() if abs(r.imag)<1e-7 and -1e-9<=r.real<=duration+1e-9]
            roots=[min(duration,max(0.,r)) for r in roots]
            # Direct companion-matrix roots differ from production derivative
            # bracketing; derivative roots additionally expose tangencies.
            for r in poly.deriv().roots():
                if abs(r.imag)<1e-8 and 0<=r.real<=duration and abs(poly(r.real))<1e-9:
                    roots.append(float(r.real))
            nodes=sorted(set([0.,duration,*roots]))
            for l,r in zip(nodes,nodes[1:]):
                if poly((l+r)/2)<0:raw.append((start+l,start+r))
            for t in nodes:
                if poly(t)<=0 or t in roots:raw.append((start+t,start+t))
    merged=[]
    for s,e in sorted(raw):
        if merged and s<=merged[-1][1]:merged[-1]=(merged[-1][0],max(e,merged[-1][1]))
        else:merged.append((s,e))
    return merged


def state_at_piece(piece,time):
    t=time-piece['start_time'];v=np.array(piece['velocity']);a=np.array(piece['acceleration'])
    return np.array(piece['position'])+v*t+.5*a*t*t,v+a*t


def latest_departures(M,records,time,left=False):
    edges=[(r['agents'][0],r['agents'][1],s,e) for r in records for s,e in r['effective'] if not left or s<time]
    clocks=np.zeros((M,M))
    for receiver in range(M):
        latest=np.full(M,-np.inf);latest[receiver]=time
        for _ in range(M*len(edges)+1):
            changed=False
            for m,n,s,e in edges:
                for source,target in ((m,n),(n,m)):
                    departure=min(latest[target],e)
                    if departure>=s and departure>latest[source]:latest[source]=departure;changed=True
            if not changed:break
        clocks[receiver]=np.maximum(latest,0.)
    return clocks


def independent_delta(M,records,T):
    events=sorted(set([0.,T,*[t for r in records for s,e in r['effective'] for t in (s,e)]]))
    peak=0.
    for t in events:
        for left in (False,True):
            clock=latest_departures(M,records,t,left)
            for m in range(M):
                for n in range(M):
                    if m!=n:peak=max(peak,t-clock[n,m])
    return peak


def validate_solution(data,solution,require_feasible=True):
    import copy
    one=copy.deepcopy(data);one['front']=[solution];one['statistics']={}
    motion=validate_motion(one);c=data['config'];M=len(solution['trajectories']);T=max(solution['completion_times'])
    assert solution['motion_budget_valid'] and solution['validation_status']=='valid'
    declared={}
    for m,(route,times,tr) in enumerate(zip(solution['routes'],solution['visit_times'],solution['trajectories'])):
        assert len(route)==len(times)
        for v,(arrival,departure) in zip(route,times):
            assert 0<=arrival<=departure<=tr['completion_time']+2e-6
            assert departure-arrival>=v['wait']-2e-6
            for t in (arrival,departure):
                p,vel=state_at(tr,t)
                assert max(abs(p-np.array(v['position'])))<2e-6
                assert max(abs(vel-np.array(v['velocity'])))<2e-6
            if departure>arrival+2e-6:assert v['velocity']==[0,0]
            declared[v['id']]=(m,v,arrival,departure)
    for meeting in solution['meetings']:
        m,a,ta,da=declared[meeting['left']];n,b,tb,db=declared[meeting['right']]
        assert m!=n and a['velocity']==b['velocity']==[0,0]
        assert np.linalg.norm(np.array(a['position'])-b['position'])<=c['comm_range']+2e-6
        assert min(da,db)-max(ta,tb)>=c['handshake_time']-2e-6
    recomputed=[]
    for m in range(M):
        for n in range(m+1,M):
            raw=independent_contacts(solution['trajectories'][m],solution['trajectories'][n],T,c['comm_range'])
            effective=[(s,e) if s==0 else (s+c['handshake_time'],e) for s,e in raw if s==0 or e-s>=c['handshake_time']]
            recomputed.append({'agents':[m,n],'raw':raw,'effective':effective})
    original=solution['communication']['contacts']
    assert len(original)==len(recomputed)
    for a,b in zip(original,recomputed):
        assert a['agents']==b['agents']
        for key in ('raw','effective'):
            assert len(a[key])==len(b[key]),(key,a,b)
            if a[key]:assert np.max(np.abs(np.array(a[key])-np.array(b[key])))<2e-6
    peak=independent_delta(M,recomputed,T)
    assert abs(peak-solution['peak_staleness'])<2e-6,(peak,solution['peak_staleness'])
    assert abs(max(0.,peak-c['recurrence_bound'])-solution['comm_violation'])<2e-6
    if require_feasible:
        assert solution['feasible'] and peak<=c['recurrence_bound']+2e-6
    assert np.max(np.abs(latest_departures(M,original,T)-np.array(solution['communication']['final_clock'])))<2e-6
    for time,left,event in solution['communication']['history']:
        for is_left,value in ((True,left),(False,event)):
            H=latest_departures(M,original,time,is_left)
            ages=[time-H[n,m] for n in range(M) for m in range(M) if m!=n]
            assert abs(max(ages,default=0.)-value)<2e-6
    return {**motion,'independent_delta':peak}


def validate(data,include_bank=False):
    validate_motion(data)
    checked=[]
    for s in data['front']:checked.append(validate_solution(data,s))
    if include_bank:
        for s in data.get('candidate_bank',[]):checked.append(validate_solution(data,s,False))
    return {'solutions_checked':len(checked),'motion_pieces_checked':sum(x['motion_pieces_checked'] for x in checked),
            'max_motion_residual':max((x['max_residual'] for x in checked),default=0.),'front_size':len(data['front']),
            'bank_checked':include_bank,'communication_method':'independent companion polynomial roots + backwards latest-departure reachability'}


if __name__=='__main__':
    import sys
    print(json.dumps(validate(json.loads(Path(sys.argv[1]).read_text())),indent=2))
