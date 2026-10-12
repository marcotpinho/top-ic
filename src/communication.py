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
    pair_peaks: tuple[tuple[float,...],...] = ()  # receiver, source
    integrated_excess: float = 0.  # pair-time above the configured Tc; search guidance only


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


def sweep(num_agents,horizon,records,recurrence_bound=None):
    if num_agents<1 or horizon<0:
        raise ValueError('Invalid mission dimensions')
    links=[(m,n,s,e) for record in records for m,n in [record.agents] for s,e in record.effective]
    if any(not (0<=m<n<num_agents and 0<=s<=e<=horizon) for m,n,s,e in links):
        raise ValueError('Invalid effective link')
    breakpoints=sorted(set([0.,horizon,*[t for _,_,s,e in links for t in (s,e)]]))
    clock=np.zeros((num_agents,num_agents));history=[];delta=0.;bottleneck=None
    mask=~np.eye(num_agents,dtype=bool)
    pair_peaks=np.zeros((num_agents,num_agents))
    excess=0.
    previous_ages=np.zeros((num_agents,num_agents))
    def age(time,phase):
        nonlocal delta,bottleneck
        if num_agents==1:return 0.
        ages=np.where(mask,time-clock,-np.inf);value=float(np.max(ages))
        np.maximum(pair_peaks,np.where(mask,ages,0.),out=pair_peaks)
        if value>delta:
            receiver,source=np.unravel_index(np.argmax(ages),ages.shape)
            delta=value;bottleneck=(int(source),int(receiver),float(time),phase)
        return value
    previous=0.
    for t in breakpoints:
        if t>previous:
            middle=(previous+t)/2
            propagate(clock,t,[(m,n) for m,n,s,e in links if s<middle<e])
        left_ages=np.where(mask,t-clock,0.)
        if recurrence_bound is not None and t>previous:
            # Ages are affine between contact events. Integrate the positive
            # part of each directed pair's line exactly, including crossings.
            start=previous_ages[mask]-recurrence_bound
            end=left_ages[mask]-recurrence_bound
            duration=t-previous
            both=np.logical_and(start>0,end>0)
            rising=np.logical_and(start<=0,end>0)
            falling=np.logical_and(start>0,end<=0)
            excess+=float(np.sum((start[both]+end[both])*duration/2))
            excess+=float(np.sum(end[rising]**2*duration/(2*(end[rising]-start[rising]))))
            excess+=float(np.sum(start[falling]**2*duration/(2*(start[falling]-end[falling]))))
        left=age(t,'left')
        propagate(clock,t,[(m,n) for m,n,s,e in links if s<=t<=e])
        exact=age(t,'event');history.append((float(t),left,exact));previous=t
        previous_ages=np.where(mask,t-clock,0.)
    return CommunicationResult(delta,tuple(records),tuple(history),tuple(tuple(float(x) for x in row) for row in clock),bottleneck,
                               pair_peaks=tuple(tuple(float(x) for x in row) for row in pair_peaks),
                               integrated_excess=excess)


def evaluate_communication(trajectories,radius,handshake,recurrence_bound=None):
    horizon=max(t.completion_time for t in trajectories)
    records=[]
    for m in range(len(trajectories)):
        for n in range(m+1,len(trajectories)):
            raw=pair_contacts(trajectories[m],trajectories[n],horizon,radius)
            records.append(ContactRecord((m,n),raw,effective_intervals(raw,handshake)))
    return sweep(len(trajectories),horizon,records,recurrence_bound)
