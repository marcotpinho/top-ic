"""Continuous passage, flight-time accounting, and deterministic scoring."""
from dataclasses import dataclass, replace
from math import inf
import numpy as np
from .trajectory import State, MotionPiece, AgentTrajectory, connect, MotionError


@dataclass(frozen=True)
class Evaluation:
    valid: bool
    objectives: tuple[float,float]
    completion_times: tuple[float,...]
    reached_tasks: tuple[frozenset[str],...]
    trajectories: tuple[AgentTrajectory,...]
    reason: str = ""
    peak_staleness: float | None = None
    first_visitors: tuple[tuple[str,int,float],...] = ()
    motion_budget_valid: bool = False
    comm_violation: float = 0.
    communication: object = None
    visit_times: tuple = ()
    validation_status: str = "valid"

    @property
    def reward(self):
        return -self.objectives[0]


def passage_time(piece, point, tolerance=2e-7):
    differences=tuple(p-z for p,z in zip(piece.position,point))
    axis=max(range(2),key=lambda d:abs(differences[d])+abs(piece.velocity[d])+abs(piece.acceleration[d]))
    coeff=[.5*piece.acceleration[axis],piece.velocity[axis],differences[axis]]
    while len(coeff)>1 and abs(coeff[0])<1e-13:
        coeff.pop(0)
    if len(coeff)==1:
        candidates=[0.,piece.duration] if abs(coeff[0])<=tolerance else []
    else:
        candidates=[float(r.real) for r in np.roots(coeff) if abs(r.imag)<1e-8]
        candidates.extend([0.,piece.duration])
    valid=[]
    for t in candidates:
        if -1e-9<=t<=piece.duration+1e-9:
            t=min(piece.duration,max(0.,t))
            if max(abs(p-z) for p,z in zip(piece.state(t).position,point))<=tolerance:
                valid.append(piece.start_time+t)
    return min(valid) if valid else None


class Evaluator:
    def __init__(self,problem,allow_team=False,config=None):
        self.problem=problem
        self.allow_team=allow_team
        self.cache={}
        self.config=config
        self.icc=config is not None and config.mode=="team_kop_icc"

    def evaluate(self,solution):
        identities=[v.id for route in solution.routes for v in route]
        if len(identities)!=len(set(identities)):
            return replace(solution,evaluation=Evaluation(False,(inf,inf),(),(),(),"Visit occurrence IDs must be unique",validation_status="invalid"))
        if solution.key in self.cache:
            return replace(solution,evaluation=self.cache[solution.key])
        try:
            result=self._evaluate(solution)
        except (MotionError,ValueError) as exc:
            result=Evaluation(False,(inf,inf),(),(),(),str(exc),validation_status="unresolved" if exc.__class__.__name__=="ContactUncertain" else "invalid")
        self.cache[solution.key]=result
        return replace(solution,evaluation=result)

    def _evaluate(self,solution):
        problem=self.problem
        if len(solution.routes)!=problem.num_agents or (problem.num_agents!=1 and not self.allow_team):
            raise ValueError("This stage supports one agent; route counts must match")
        if solution.meetings and not self.icc:
            raise ValueError("Planned meetings require communication mode")
        if any(len(route)<2 for route in solution.routes):raise ValueError("Route needs START and END")
        timing=None
        if self.icc:
            from .scheduling import schedule
            timing,_=schedule(solution.routes,solution.meetings,problem,self.config.handshake_time,self.config.comm_range)
        trajectories=[]
        visit_times=[]
        sets=[]
        owners={}
        ids=[]
        for m,route in enumerate(solution.routes):
            if len(route)<2 or route[0].kind!="START" or route[-1].kind!="END":
                raise ValueError("Route must begin START and terminate END")
            if route[0].position!=problem.start or route[0].velocity!=problem.initial_velocities[m] or route[-1].position!=problem.end or route[-1].velocity!=(0.,0.) or route[-1].wait!=0:
                raise ValueError("Invalid boundary states")
            for visit in route:
                ids.append(visit.id)
                if visit.kind=="FREE":
                    if not self.icc:raise ValueError("Free visits require communication mode")
                    workspace=self.config.waypoint_workspace
                    if workspace and not (workspace[0]<=visit.position[0]<=workspace[1] and workspace[2]<=visit.position[1]<=workspace[3]):
                        raise ValueError("Free waypoint outside configured workspace")
                if visit.kind=="TASK" and (visit.task_id not in problem.task_map or visit.position!=problem.task_map[visit.task_id].position):
                    raise ValueError("Invalid fixed task position")
            if any(v.kind not in (("TASK","FREE") if self.icc else ("TASK",)) for v in route[1:-1]):
                raise ValueError("Invalid interior visit")
            if self.icc and sum(v.kind=="FREE" for v in route)>self.config.max_free_waypoints:
                raise ValueError("Free-waypoint cap exceeded")
            pieces=[]
            elapsed=0.
            times=[]
            for k,(start,end) in enumerate(zip(route,route[1:])):
                wait=start.wait if timing is None else timing[m][k][1]-timing[m][k][0]
                times.append((elapsed,elapsed+wait))
                if wait>1e-10:
                    if start.velocity!=(0.,0.):raise ValueError("Scheduled waiting requires a stopped state")
                    pieces.append(MotionPiece(start.position,start.velocity,(0.,0.),wait,elapsed))
                    elapsed+=wait
                connection=connect(State(start.position,start.velocity),State(end.position,end.velocity),problem.limits[m])
                pieces.extend(replace(p,start_time=p.start_time+elapsed) for p in connection.pieces)
                elapsed+=connection.duration
            times.append((elapsed,elapsed));visit_times.append(tuple(times))
            trajectory=AgentTrajectory(tuple(pieces),elapsed,State(route[0].position,route[0].velocity),State(route[-1].position,route[-1].velocity))
            trajectories.append(trajectory)
            reached=set()
            for task in problem.tasks:
                times=[t for p in pieces if (t:=passage_time(p,task.position)) is not None]
                if task.position==trajectory.start.position:
                    times.append(0.)
                if task.position==trajectory.end.position:
                    times.append(elapsed)
                if times:
                    reached.add(task.id)
                    record=(min(times),m)
                    if task.id not in owners or record<owners[task.id]:
                        owners[task.id]=record
            sets.append(frozenset(reached))
        if len(ids)!=len(set(ids)):
            raise ValueError("Visit occurrence IDs must be unique")
        completions=tuple(t.completion_time for t in trajectories)
        reward=sum(task.reward for task in problem.tasks if task.id in set().union(*sets))
        feasible=all(c<=b+1e-7 for c,b in zip(completions,problem.time_budgets))
        communication=None;violation=0.;reason="" if feasible else "Individual flight-time budget exceeded"
        physical=feasible
        if feasible and self.icc:
            from .communication import evaluate_communication
            communication=evaluate_communication(tuple(trajectories),self.config.comm_range,self.config.handshake_time)
            violation=max(0.,communication.peak_staleness-self.config.recurrence_bound)
            feasible=violation==0.
            if not feasible:reason="Communication recurrence bound exceeded"
        return Evaluation(feasible,(-reward,sum(completions)/len(completions)),completions,tuple(sets),tuple(trajectories),
                          reason,communication.peak_staleness if communication else (0. if problem.num_agents==1 else None),
                          tuple((task,m,t) for task,(t,m) in sorted(owners.items())),physical,violation,communication,tuple(visit_times))
