"""Stage-4 comparisons and communication timelines from portable JSON."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
from .viz_team import plot_result


def plot_fronts(named,destination,title):
    fig,ax=plt.subplots(figsize=(9,6))
    for label,front in named.items():
        ordered=sorted(front,key=lambda s:s['objectives'][1])
        ax.plot([s['objectives'][1] for s in ordered],[s['reward'] for s in ordered],'.-',label=label)
    ax.set(xlabel='Mean completion time (s; minimize)',ylabel='Unique team reward (maximize)',title=title)
    ax.grid(alpha=.25);ax.legend(fontsize=8);fig.tight_layout();fig.savefig(destination,dpi=160);plt.close(fig)


def plot_communication(data,directory,prefix='full'):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    if not data['front']:return
    chosen=max(data['front'],key=lambda s:(s['reward'],-s['objectives'][1]))
    # Reuse actual quadratic paths / speed rendering; add free-visit markers
    # and planned meeting positions to a separate geometry figure.
    plot_result(data,directory,prefix)
    fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True)
    records=chosen['communication']['contacts']
    for i,record in enumerate(records):
        for s,e in record['raw']:axes[0].plot([s,e],[i,i],color='lightgray',linewidth=7)
        for s,e in record['effective']:axes[0].plot([s,e],[i,i],color='tab:blue',linewidth=3,marker='.' if s==e else None)
    axes[0].set(yticks=range(len(records)),yticklabels=[f"{r['agents'][0]+1}–{r['agents'][1]+1}" for r in records],ylabel='Agent pair',title='Raw contacts (gray), usable links after handshake (blue)')
    trace=chosen['communication']['history'];times=[];ages=[]
    for t,left,event in trace:times.extend([t,t]);ages.extend([left,event])
    axes[1].plot(times,ages,label='Peak instantaneous information age')
    axes[1].axhline(data['config']['recurrence_bound'],color='tab:red',linestyle='--',label='Tc')
    for m,c in enumerate(chosen['completion_times']):axes[1].axvline(c,color='gray',alpha=.3)
    axes[1].set(xlabel='Mission time (s)',ylabel='Information staleness (s)',title=f"Supremum Δ={chosen['peak_staleness']:.4g}s; arrival markers include free terminal presence")
    axes[1].legend();axes[1].grid(alpha=.25);fig.tight_layout();fig.savefig(directory/f'{prefix}-communication.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,7));problem=data['problem']
    ax.scatter([t['position'][0] for t in problem['tasks']],[t['position'][1] for t in problem['tasks']],color='gray',marker='.',label='Tasks')
    for m,tr in enumerate(chosen['trajectories']):
        positions=[]
        for piece in tr['pieces']:
            t=np.linspace(0,piece['duration'],30)[:,None]
            positions.extend(np.array(piece['position'])+t*np.array(piece['velocity'])+.5*t*t*np.array(piece['acceleration']))
        if positions:
            points=np.array(positions);ax.plot(points[:,0],points[:,1],label=f'Agent {m+1}')
        for v in chosen['routes'][m]:
            if v['kind']=='FREE':ax.scatter(*v['position'],marker='D',facecolors='none',edgecolors='tab:red',s=70)
    ax.scatter(*problem['start'],marker='s',color='black',label='Start');ax.scatter(*problem['end'],marker='*',color='black',s=100,label='End')
    ax.scatter([],[],marker='D',facecolors='none',edgecolors='tab:red',label='Free waypoint')
    ax.set(xlabel='x (m)',ylabel='y (m)',title='Continuous paths and freely positioned rendezvous visits');ax.set_aspect('equal');ax.legend();ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(directory/f'{prefix}-free-waypoints.png',dpi=160);plt.close(fig)
