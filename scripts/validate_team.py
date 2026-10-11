"""Independent algebraic checks of saved trajectories, no connector/evaluator calls."""
import json,math
from pathlib import Path
import numpy as np

def validate(data):
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
                assert visit['kind']=='TASK' and visit['task_id'] in visits
                task=next(t for t in problem['tasks'] if t['id']==visit['task_id'])
                assert visit['position']==task['position']
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

if __name__=='__main__':
    import sys
    print(json.dumps(validate(json.loads(Path(sys.argv[1]).read_text())),indent=2))
