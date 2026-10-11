"""Least stopped-rendezvous schedule over fixed kinematic connection times."""
from .trajectory import State,connect


class ScheduleError(ValueError):
    pass


def schedule(routes,meetings,problem,handshake,radius):
    offsets=[];count=1
    for route in routes:
        offsets.append(count);count+=2*len(route)
    def arrival(m,k):return offsets[m]+2*k
    def departure(m,k):return offsets[m]+2*k+1
    edges=[];visits={};durations=[]
    for m,route in enumerate(routes):
        edges.append((0,arrival(m,0),0.))
        for k,v in enumerate(route):
            if v.id in visits:raise ScheduleError('Duplicate visit ID')
            visits[v.id]=(m,k,v)
            edges.append((arrival(m,k),departure(m,k),v.wait))
        connection_times=[]
        for k,(first,second) in enumerate(zip(route,route[1:])):
            duration=connect(State(first.position,first.velocity),State(second.position,second.velocity),problem.limits[m]).duration
            connection_times.append(duration)
            edges.extend([(departure(m,k),arrival(m,k+1),duration),(arrival(m,k+1),departure(m,k),-duration)])
        durations.append(tuple(connection_times))
    for meeting in meetings:
        if meeting.left not in visits or meeting.right not in visits:
            raise ScheduleError('Dangling meeting reference')
        m,k,a=visits[meeting.left];n,j,b=visits[meeting.right]
        if m==n or a.kind=='END' or b.kind=='END' or a.velocity!=(0.,0.) or b.velocity!=(0.,0.):
            raise ScheduleError('Meeting requires stopped nonterminal visits of distinct agents')
        if sum((x-y)**2 for x,y in zip(a.position,b.position))>radius**2:
            raise ScheduleError('Planned meeting positions outside range')
        for x,y in ((arrival(m,k),departure(m,k)),(arrival(n,j),departure(n,j)),(arrival(m,k),departure(n,j)),(arrival(n,j),departure(m,k))):
            edges.append((x,y,handshake))
    values=[0.]*count
    for _ in range(count):
        changed=False
        for a,b,w in edges:
            proposed=values[a]+w
            if proposed>values[b]:
                values[b]=proposed;changed=True
        if not changed:break
    else:raise ScheduleError('Positive-cycle rendezvous deadlock')
    timing=[]
    for m,route in enumerate(routes):
        pairs=tuple((values[arrival(m,k)],values[departure(m,k)]) for k in range(len(route)))
        if pairs[0][0]!=0 or abs(pairs[-1][1]-pairs[-1][0])>1e-8:
            raise ScheduleError('Invalid pinned/terminal time')
        timing.append(pairs)
    return tuple(timing),tuple(durations)
