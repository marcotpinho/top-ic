"""Portable Pareto and continuous trajectory plots for saved KOP results."""
import numpy as np
from matplotlib import pyplot as plt

def plot_result(data_orpath, output_dir):
    """Plot saved full trajectories; no straight-line route approximation."""
    import json
    from pathlib import Path
    data = json.loads(Path(data_orpath).read_text()) if isinstance(data_orpath, (str, Path)) else data_orpath
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    front = data['front']
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter([s['objectives'][1] for s in front], [s['reward'] for s in front])
    ax.set(xlabel='Average completion time (s; minimize)', ylabel='Team reward (maximize)', title='Epsilon-box archive representatives' if data.get('statistics',{}).get('archive_policy')=='epsilon_box_dominance' else 'Nondominated solutions')
    ax.grid(alpha=.25); fig.tight_layout(); fig.savefig(out/'pareto.png', dpi=150); plt.close(fig)
    if not front: return
    chosen = max(front, key=lambda s: (s['reward'], -s['objectives'][1]))
    problem=data['problem']; fig,ax=plt.subplots(figsize=(7,7)); fig2, speed=plt.subplots(figsize=(8,4))
    tasks=problem['tasks']; task_scatter=ax.scatter([t['position'][0] for t in tasks], [t['position'][1] for t in tasks], c=[t['reward'] for t in tasks], cmap='viridis', marker='D', label='Tasks')
    fig.colorbar(task_scatter,ax=ax,shrink=.6,label='Task reward')
    for task in tasks: ax.annotate(task['id'], task['position'], xytext=(4,4), textcoords='offset points',fontsize=7)
    for label,key,marker in [('Start','start','s'),('End','end','X')]: ax.scatter(*problem[key],marker=marker,s=100,label=label)
    for m,trajectory in enumerate(chosen['trajectories']):
        points=[]; velocities=[]; times=[]
        for piece in trajectory['pieces']:
            local=np.linspace(0,piece['duration'],max(3,int(piece['duration']*20)+2))
            p=np.asarray(piece['position']); v=np.asarray(piece['velocity']); a=np.asarray(piece['acceleration'])
            points.extend(p+local[:,None]*v+.5*local[:,None]**2*a)
            velocities.extend(v+local[:,None]*a); times.extend(local+piece['start_time'])
        if points:
            points=np.asarray(points); velocities=np.asarray(velocities)
            ax.plot(points[:,0],points[:,1],label=f'Agent {m+1}')
            # Plot components: model has axis limits, not a Euclidean speed cap.
            speed.plot(times,velocities[:,0],label=f'Agent {m+1} vx');speed.plot(times,velocities[:,1],linestyle='--',label=f'Agent {m+1} vy')
    ax.set(title=f"Highest reward archive solution: {chosen['reward']:g}; mean time {chosen['objectives'][1]:.3f}s",xlabel='x (m)',ylabel='y (m)');ax.set_aspect('equal');ax.grid(alpha=.2);ax.legend(fontsize=8)
    speed.set(xlabel='Time (s)',ylabel='Velocity components (m/s)',title='Continuous piecewise acceleration trajectory');speed.grid(alpha=.2);speed.legend(fontsize=8)
    fig.tight_layout();fig.savefig(out/'paths.png',dpi=150);plt.close(fig)
    fig2.tight_layout();fig2.savefig(out/'speed.png',dpi=150);plt.close(fig2)


def plot_comparison(named_results, output_path):
    fig, ax = plt.subplots(figsize=(9,6))
    for name,data in named_results:
        front=sorted(data['front'],key=lambda s:s['objectives'][1])
        ax.plot([s['objectives'][1] for s in front],[s['reward'] for s in front],marker='.',label=name,alpha=.8)
    ax.set(xlabel='Average completion time (s; minimize)',ylabel='Reward (maximize)',title='Matched-budget epsilon archive fronts');ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.tight_layout();fig.savefig(output_path,dpi=150);plt.close(fig)
