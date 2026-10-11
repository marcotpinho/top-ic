"""Lazy occurrence-level KOP neighborhoods with deterministic enumeration."""
from dataclasses import replace
from .config import velocity_menu
from .solution import Solution, Visit

SINGLE_NEIGHBORHOODS=("insert","remove","replace","reorder","velocity")
TEAM_NEIGHBORHOODS=SINGLE_NEIGHBORHOODS+("assignment",)


def normalize(routes):
    # Occurrence IDs are stable for a particular order and canonical across edits.
    return Solution(tuple(tuple(replace(v,id=f"{m}:{k}") for k,v in enumerate(r)) for m,r in enumerate(routes)))


def edited(solution,m,route):
    routes=list(solution.routes);routes[m]=tuple(route)
    return normalize(routes)


def neighbors(solution,problem,config,family):
    reached=set().union(*solution.evaluation.reached_tasks) if solution.evaluation else set()
    for m,route in enumerate(solution.routes):
        menu=velocity_menu(problem.limits[m],config)
        if family=="insert":
            for task in problem.tasks:
                if task.id in reached: continue
                for k in range(1,len(route)):
                    for velocity in menu:
                        visit=Visit("new","TASK",task.position,velocity,task.id)
                        yield edited(solution,m,route[:k]+(visit,)+route[k:])
        elif family=="remove":
            for k in range(1,len(route)-1):
                yield edited(solution,m,route[:k]+route[k+1:])
        elif family=="replace":
            for k in range(1,len(route)-1):
                for task in problem.tasks:
                    if task.id in reached: continue
                    for velocity in menu:
                        yield edited(solution,m,route[:k]+(Visit("new","TASK",task.position,velocity,task.id),)+route[k+1:])
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
                    for j in range(1,len(other)):
                        for velocity in target_menu:
                            routes=list(solution.routes)
                            routes[m]=route[:k]+route[k+1:]
                            routes[n]=other[:j]+(replace(route[k],velocity=velocity,wait=0.),)+other[j:]
                            yield normalize(routes)
                    if m<n:
                        for j in range(1,len(other)-1):
                            # Enumerate both new states, not old velocities that
                            # may violate another agent's limits.
                            for vm in menu:
                                for vn in target_menu:
                                    routes=list(solution.routes)
                                    routes[m]=route[:k]+(replace(other[j],velocity=vm,wait=0.),)+route[k+1:]
                                    routes[n]=other[:j]+(replace(route[k],velocity=vn,wait=0.),)+other[j+1:]
                                    yield normalize(routes)
                if m<n:
                    for i in range(1,len(route)):
                        for j in range(1,len(other)):
                            # Tail exchange includes task-state reset to avoid
                            # importing incompatible heterogeneous velocities.
                            routes=list(solution.routes)
                            routes[m]=route[:i]+tuple(replace(v,velocity=(0.,0.),wait=0.) for v in other[j:-1])+(route[-1],)
                            routes[n]=other[:j]+tuple(replace(v,velocity=(0.,0.),wait=0.) for v in route[i:-1])+(other[-1],)
                            yield normalize(routes)
