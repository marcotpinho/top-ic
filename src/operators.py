"""Lazy occurrence-level KOP neighborhoods with deterministic enumeration."""
from dataclasses import replace
from .config import velocity_menu
from .solution import Solution, Visit, Meeting

SINGLE_NEIGHBORHOODS=("insert","remove","replace","reorder","velocity")
TEAM_NEIGHBORHOODS=SINGLE_NEIGHBORHOODS+("assignment",)
COMM_NEIGHBORHOODS=("wait","meeting","free_move","free_remove")
ICC_NEIGHBORHOODS=TEAM_NEIGHBORHOODS+COMM_NEIGHBORHOODS


def normalize(routes,meetings=()):
    # Preserve occurrence identity across order/assignment edits. Only fresh
    # placeholder collisions receive deterministic unused IDs.
    used=set();rebuilt=[]
    for m,route in enumerate(routes):
        row=[]
        for k,v in enumerate(route):
            identity=v.id
            if identity in used:
                suffix=0
                while f"{identity}#{suffix}" in used:suffix+=1
                identity=f"{identity}#{suffix}"
                v=replace(v,id=identity)
            used.add(identity);row.append(v)
        rebuilt.append(tuple(row))
    ownership={v.id:m for m,r in enumerate(rebuilt) for v in r}
    kept=tuple(p for p in meetings if p.left in used and p.right in used and ownership[p.left]!=ownership[p.right])
    return Solution(tuple(rebuilt),meetings=kept)


def fresh_id(solution,prefix):
    used={v.id for r in solution.routes for v in r};i=0
    while f"{prefix}:{i}" in used:i+=1
    return f"{prefix}:{i}"


def edited(solution,m,route):
    routes=list(solution.routes);routes[m]=tuple(route)
    return normalize(routes,solution.meetings)


def neighbors(solution,problem,config,family):
    if family in COMM_NEIGHBORHOODS:
        yield from communication_neighbors(solution,problem,config,family)
        return
    reached=set().union(*solution.evaluation.reached_tasks) if solution.evaluation else set()
    for m,route in enumerate(solution.routes):
        menu=velocity_menu(problem.limits[m],config)
        if family=="insert":
            for task in problem.tasks:
                if task.id in reached: continue
                for k in range(1,len(route)):
                    for velocity in menu:
                        visit=Visit(fresh_id(solution,"task"),"TASK",task.position,velocity,task.id)
                        yield edited(solution,m,route[:k]+(visit,)+route[k:])
        elif family=="remove":
            for k in range(1,len(route)-1):
                if route[k].kind=="TASK":yield edited(solution,m,route[:k]+route[k+1:])
        elif family=="replace":
            for k in range(1,len(route)-1):
                if route[k].kind!="TASK":continue
                for task in problem.tasks:
                    if task.id in reached: continue
                    for velocity in menu:
                        yield edited(solution,m,route[:k]+(Visit(fresh_id(solution,"task"),"TASK",task.position,velocity,task.id),)+route[k+1:])
        elif family=="reorder":
            for i in range(1,len(route)-1):
                for j in range(1,len(route)-1):
                    if i==j: continue
                    visits=list(route);v=visits.pop(i);visits.insert(j,v)
                    yield edited(solution,m,tuple(visits))
                for j in range(i+2,len(route)):
                    yield edited(solution,m,route[:i]+tuple(reversed(route[i:j]))+route[j:])
        elif family=="velocity":
            for k in range(1,len(route)-1):
                for velocity in menu:
                    if velocity!=route[k].velocity:
                        yield edited(solution,m,route[:k]+(replace(route[k],velocity=velocity,wait=0.),)+route[k+1:])
            for k,v in enumerate(route[:-1]):
                if v.wait>0:
                    yield edited(solution,m,route[:k]+(replace(v,wait=0.),)+route[k+1:])
        elif family=="assignment":
            for n,other in enumerate(solution.routes):
                if n==m:continue
                target_menu=velocity_menu(problem.limits[n],config)
                for k in range(1,len(route)-1):
                    if route[k].kind!="TASK":continue
                    for j in range(1,len(other)):
                        for velocity in target_menu:
                            routes=list(solution.routes)
                            routes[m]=route[:k]+route[k+1:]
                            routes[n]=other[:j]+(replace(route[k],velocity=velocity,wait=0.),)+other[j:]
                            yield normalize(routes,solution.meetings)
                    if m<n:
                        for j in range(1,len(other)-1):
                            if other[j].kind!="TASK":continue
                            # Enumerate both new states, not old velocities that
                            # may violate another agent's limits.
                            for vm in menu:
                                for vn in target_menu:
                                    routes=list(solution.routes)
                                    routes[m]=route[:k]+(replace(other[j],velocity=vm,wait=0.),)+route[k+1:]
                                    routes[n]=other[:j]+(replace(route[k],velocity=vn,wait=0.),)+other[j+1:]
                                    yield normalize(routes,solution.meetings)
                if m<n:
                    for i in range(1,len(route)):
                        for j in range(1,len(other)):
                            # Tail exchange includes task-state reset to avoid
                            # importing incompatible heterogeneous velocities.
                            routes=list(solution.routes)
                            routes[m]=route[:i]+tuple(replace(v,velocity=(0.,0.),wait=0.) for v in other[j:-1])+(route[-1],)
                            routes[n]=other[:j]+tuple(replace(v,velocity=(0.,0.),wait=0.) for v in route[i:-1])+(other[-1],)
                            yield normalize(routes,solution.meetings)


def communication_neighbors(solution,problem,config,family):
    from math import hypot
    if config.mode!="team_kop_icc":return
    if family=="wait":
        for m,route in enumerate(solution.routes):
            for k,v in enumerate(route[:-1]):
                if k==0 and problem.initial_velocities[m]!=(0.,0.):continue
                for step in config.wait_steps:
                    for wait in sorted(set([0.,v.wait+step,max(0.,v.wait-step)])):
                        changed=replace(v,velocity=(0.,0.),wait=wait)
                        if changed!=v:yield edited(solution,m,route[:k]+(changed,)+route[k+1:])
    elif family=="free_remove":
        for pair in solution.meetings:
            yield normalize(solution.routes,tuple(p for p in solution.meetings if p!=pair))
        for m,route in enumerate(solution.routes):
            for k,v in enumerate(route[1:-1],1):
                if v.kind=="FREE":yield edited(solution,m,route[:k]+route[k+1:])
    elif family=="free_move":
        positions={v.id:(m,k,v) for m,r in enumerate(solution.routes) for k,v in enumerate(r)}
        groups=[(v.id,) for r in solution.routes for v in r if v.kind=="FREE"]
        groups.extend((p.left,p.right) for p in solution.meetings if all(positions[x][2].kind=="FREE" for x in (p.left,p.right)))
        for group in groups:
            for step in config.waypoint_steps:
                for dx,dy in ((step,0),(-step,0),(0,step),(0,-step)):
                    routes=[list(r) for r in solution.routes]
                    allowed=True
                    for identity in group:
                        m,k,v=positions[identity];point=(v.position[0]+dx,v.position[1]+dy)
                        if config.waypoint_workspace is not None:
                            xmin,xmax,ymin,ymax=config.waypoint_workspace
                            if not (xmin<=point[0]<=xmax and ymin<=point[1]<=ymax):allowed=False;break
                        routes[m][k]=replace(v,position=point)
                    if allowed:yield normalize(routes,solution.meetings)
    elif family=="meeting":
        ev=solution.evaluation
        for m,route in enumerate(solution.routes):
            for n in range(m+1,len(solution.routes)):
                other=solution.routes[n]
                # Link existing task/free visits: explicit stop states make the
                # stationary handshake physically meaningful.
                for k,a in enumerate(route[:-1]):
                    if k==0 and a.velocity!=(0.,0.):continue
                    for j,b in enumerate(other[:-1]):
                        if j==0 and b.velocity!=(0.,0.):continue
                        if hypot(a.position[0]-b.position[0],a.position[1]-b.position[1])>config.comm_range:continue
                        pair=Meeting(a.id,b.id)
                        if pair in solution.meetings:continue
                        routes=[list(r) for r in solution.routes]
                        routes[m][k]=replace(a,velocity=(0.,0.));routes[n][j]=replace(b,velocity=(0.,0.))
                        yield normalize(routes,solution.meetings+(pair,))
                time=(max(0.,ev.communication.bottleneck[2]-ev.peak_staleness/2) if ev and ev.communication and ev.communication.bottleneck else max(ev.completion_times)/2 if ev else 0.)
                pa=ev.trajectories[m].state(time).position if ev else problem.start
                pb=ev.trajectories[n].state(time).position if ev else problem.end
                midpoint=tuple((x+y)/2 for x,y in zip(pa,pb))
                points=[(midpoint,None)]
                tasks=sorted(problem.tasks,key=lambda t:(hypot(t.position[0]-midpoint[0],t.position[1]-midpoint[1]),t.id))[:4]
                points.extend((t.position,t.id) for t in tasks)
                for point,task_id in points:
                    if point==problem.end:continue
                    if task_id is None:
                        if any(sum(v.kind=="FREE" for v in r)>=config.max_free_waypoints for r in (route,other)):continue
                        if config.waypoint_workspace:
                            xmin,xmax,ymin,ymax=config.waypoint_workspace
                            if not(xmin<=point[0]<=xmax and ymin<=point[1]<=ymax):continue
                    for k in range(1,len(route)):
                        for j in range(1,len(other)):
                            left=fresh_id(solution,"rendezvous-left");right=fresh_id(solution,"rendezvous-right")
                            kind="FREE" if task_id is None else "TASK"
                            a=Visit(left,kind,point,(0.,0.),task_id);b=Visit(right,kind,point,(0.,0.),task_id)
                            routes=list(solution.routes)
                            routes[m]=route[:k]+(a,)+route[k:];routes[n]=other[:j]+(b,)+other[j:]
                            yield normalize(routes,solution.meetings+(Meeting(left,right),))
