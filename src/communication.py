"""Chronological vector-clock propagation with exact-event/left-limit phases."""
from dataclasses import dataclass
import numpy as np
from .contacts import pair_contacts,effective_intervals


@dataclass(frozen=True)
class ContactRecord:
    agents: tuple[int,int]
    raw: tuple[tuple[float,float],...]
    effective: tuple[tuple[float,float],...]


@dataclass(frozen=True)
class CommunicationResult:
    peak_staleness: float
    contacts: tuple[ContactRecord,...]
    history: tuple[tuple[float,float,float],...]  # time, left-limit peak, exact-event peak
    final_clock: tuple[tuple[float,...],...]
    bottleneck: tuple[int,int,float,str] | None  # source, receiver, time, phase
    numerical_status: str = 'resolved'


def components(num_agents,edges):
    parent=list(range(num_agents))
    def root(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]];x=parent[x]
        return x
    for m,n in edges:
        a,b=root(m),root(n)
        if a!=b:parent[b]=a
    groups={}
    for m in range(num_agents):groups.setdefault(root(m),[]).append(m)
    return list(groups.values())


def propagate(clock,time,edges):
    np.fill_diagonal(clock,time)
    for group in components(len(clock),edges):
        clock[group,:]=np.max(clock[group,:],axis=0)


def sweep(num_agents,horizon,records):
    if num_agents<1 or horizon<0:
        raise ValueError('Invalid mission dimensions')
    links=[(m,n,s,e) for record in records for m,n in [record.agents] for s,e in record.effective]
    if any(not (0<=m<n<num_agents and 0<=s<=e<=horizon) for m,n,s,e in links):
        raise ValueError('Invalid effective link')
    breakpoints=sorted(set([0.,horizon,*[t for _,_,s,e in links for t in (s,e)]]))
    clock=np.zeros((num_agents,num_agents));history=[];delta=0.;bottleneck=None
    mask=~np.eye(num_agents,dtype=bool)
    def age(time,phase):
        nonlocal delta,bottleneck
        if num_agents==1:return 0.
        ages=np.where(mask,time-clock,-np.inf);value=float(np.max(ages))
        if value>delta:
            receiver,source=np.unravel_index(np.argmax(ages),ages.shape)
            delta=value;bottleneck=(int(source),int(receiver),float(time),phase)
        return value
    previous=0.
    for t in breakpoints:
        if t>previous:
            middle=(previous+t)/2
            propagate(clock,t,[(m,n) for m,n,s,e in links if s<middle<e])
        left=age(t,'left')
        propagate(clock,t,[(m,n) for m,n,s,e in links if s<=t<=e])
        exact=age(t,'event');history.append((float(t),left,exact));previous=t
    return CommunicationResult(delta,tuple(records),tuple(history),tuple(tuple(float(x) for x in row) for row in clock),bottleneck)


def evaluate_communication(trajectories,radius,handshake):
    horizon=max(t.completion_time for t in trajectories)
    records=[]
    for m in range(len(trajectories)):
        for n in range(m+1,len(trajectories)):
            raw=pair_contacts(trajectories[m],trajectories[n],horizon,radius)
            records.append(ContactRecord((m,n),raw,effective_intervals(raw,handshake)))
    return sweep(len(trajectories),horizon,records)
