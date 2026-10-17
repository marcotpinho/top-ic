"""Portable Pareto and continuous trajectory plots for saved KOP results."""
import json
from pathlib import Path
from matplotlib import pyplot as plt
from .viz_paths import add_speed_colorbars, draw_speed_paths, draw_task_markers, save_agent_path_panels


def select_path_representatives(data):
    """Choose three reproducible views from the configured-Tc reward/time front."""
    front=data['front']
    tc=data.get('config',{}).get('recurrence_bound')
    slice_row=next((row for row in data.get('tc_slices',[]) if row['tc']==tc),None)
    if slice_row is not None:
        indices=list(slice_row['front_indices'])
    elif data.get('objective_policy')=='reward_time_violation':
        indices=[i for i,s in enumerate(front) if s['objectives'][2]==0]
    else:
        indices=list(range(len(front)))
    if not indices:
        return {}
    productive=[i for i in indices if front[i]['reward']>0]
    if productive:
        indices=productive
    highest=max(indices,key=lambda i:(front[i]['reward'],-front[i]['objectives'][1],-i))
    conservative=min(indices,key=lambda i:(front[i]['objectives'][1],-front[i]['reward'],i))
    rewards=[front[i]['reward'] for i in indices]
    times=[front[i]['objectives'][1] for i in indices]
    rmin,rmax=min(rewards),max(rewards)
    tmin,tmax=min(times),max(times)
    middle=[i for i in indices if i not in (highest,conservative)] or indices
    def tradeoff_score(i):
        reward_shortfall=(rmax-front[i]['reward'])/(rmax-rmin) if rmax>rmin else 0.
        time_excess=(front[i]['objectives'][1]-tmin)/(tmax-tmin) if tmax>tmin else 0.
        return (reward_shortfall**2+time_excess**2,-front[i]['reward'],front[i]['objectives'][1],i)
    tradeoff=min(middle,key=tradeoff_score)
    return {'max-reward':highest,'tradeoff':tradeoff,'conservative':conservative}


def select_budget_only_max_reward(data):
    """Choose the best saved route that respects flight budgets, ignoring Tc."""
    candidates=[]
    for pool in ('front','candidate_bank','dominated_archive'):
        for index,solution in enumerate(data.get(pool,[])):
            if not solution.get('motion_budget_valid',solution.get('feasible',False)):
                continue
            if solution.get('validation_status','valid')!='valid':
                continue
            candidates.append((pool,index,solution))
    if not candidates:return None
    return max(candidates,key=lambda item:(item[2]['reward'],-item[2]['objectives'][1],
                                           -(item[2].get('peak_staleness') or 0),
                                           -('front','candidate_bank','dominated_archive').index(item[0]),-item[1]))


def draw_solution_paths(problem,solution,title,output_path):
    """Render one saved solution with collected-task symbols and speed gradients."""
    fig,ax=plt.subplots(figsize=(10,7))
    tasks=problem['tasks']
    reached=set().union(*(set(ids) for ids in solution.get('reached_tasks',[])))
    task_colors=draw_task_markers(ax,tasks,reached,color_by_reward=True)
    if task_colors is not None:fig.colorbar(task_colors,ax=ax,shrink=.6,label='Task reward')
    for task in tasks:
        if len(tasks)<=30 or task['id'] in reached:
            ax.annotate(task['id'],task['position'],xytext=(4,4),textcoords='offset points',fontsize=7)
    for label,key,marker in [('Start','start','s'),('End','end','X')]:
        ax.scatter(*problem[key],marker=marker,s=100,label=label)
    sampled,speed_colors=draw_speed_paths(ax,solution['trajectories'])
    free_label=True
    for m,route in enumerate(solution['routes']):
        for visit in route:
            if visit['kind']!='FREE':continue
            ax.scatter(*visit['position'],marker='D',s=100,facecolors='none',
                       edgecolors='tab:red',linewidths=1.5,zorder=5,
                       label='Free waypoint' if free_label else None)
            ax.annotate(f'F{m+1}',visit['position'],xytext=(5,5),textcoords='offset points',fontsize=8)
            free_label=False
    ax.set(title=f"{title}: reward {solution['reward']:g}\nMean time {solution['objectives'][1]:.3f}s; Δ {(solution.get('peak_staleness') or 0):.3f}s",
           xlabel='x (m)',ylabel='y (m)')
    ax.set_aspect('equal');ax.grid(alpha=.2);ax.legend(fontsize=8)
    add_speed_colorbars(fig,ax,speed_colors)
    fig.savefig(output_path,dpi=150)
    plt.close(fig)
    return sampled,reached

def plot_objective_history(data_orpath: dict | str | Path, output_dir: str | Path) -> Path | None:
    """Plot archived objective vectors at selected search iterations."""
    data = json.loads(Path(data_orpath).read_text()) if isinstance(data_orpath, (str, Path)) else data_orpath
    history = data.get('statistics', {}).get('objective_history')
    if not history:
        return None  # Older result files did not record iteration snapshots.
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    snapshots = [row for row in history if row.get('objectives')]
    if not snapshots:
        return None
    selected = sorted(
        {round(i * (len(snapshots) - 1) / 5) for i in range(min(6, len(snapshots)))}
    )
    fig = plt.figure(figsize=(9, 7))
    ax = fig.add_subplot(111, projection='3d')
    colors = plt.get_cmap('viridis')
    denominator = max(1, len(snapshots) - 1)
    for index in selected:
        row = snapshots[index]
        vectors = row['objectives']
        ax.scatter(
            [vector[1] for vector in vectors],
            [-vector[0] for vector in vectors],
            [vector[2] for vector in vectors],
            color=colors(index / denominator),
            label=f"Iteration {row['iteration']}",
            alpha=0.8,
        )
    ax.set(
        xlabel="Mean completion time (s; minimize)",
        ylabel="Team reward (maximize)",
        zlabel="Communication violation (s; minimize)",
        title="Archive Pareto progression by iteration",
    )
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = out/'pareto-improvement.png'
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path

def plot_result(data_orpath, output_dir):
    """Plot saved full trajectories; no straight-line route approximation."""
    from pathlib import Path
    data = json.loads(Path(data_orpath).read_text()) if isinstance(data_orpath, (str, Path)) else data_orpath
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    plot_objective_history(data, out)
    if data.get('tc_slices'):
        from .viz_sweep import plot_tc_sweep
        plot_tc_sweep(data,out)
    front = data['front']
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter([s['objectives'][1] for s in front], [s['reward'] for s in front])
    ax.set(xlabel='Average completion time (s; minimize)', ylabel='Team reward (maximize)', title='Epsilon-box archive representatives' if data.get('statistics',{}).get('archive_policy')=='epsilon_box_dominance' else 'Nondominated solutions')
    ax.grid(alpha=.25); fig.tight_layout(); fig.savefig(out/'pareto.png', dpi=150); plt.close(fig)
    selected=select_path_representatives(data) if front else {}
    problem=data['problem']
    labels={'max-reward':'Maximum reward','tradeoff':'Reward–time compromise','conservative':'Minimum mean time'}
    metadata={'schema_version':2,'tc_seconds':data.get('config',{}).get('recurrence_bound'),
              'selection_rule':{'max-reward':'highest reward, then lowest mean time',
                                'tradeoff':'minimum normalized Euclidean distance to ideal reward/time point, excluding extremes when possible',
                                'conservative':'lowest mean completion time, then highest reward',
                                'eligibility':'positive reward when any positive-reward Tc-feasible solution exists',
                                'max-reward-budget-only':'highest reward among saved flight-budget-valid solutions, then lowest mean time; ignore Tc'},
              'representatives':{}}
    budget_only=select_budget_only_max_reward(data)
    if budget_only is not None:
        pool,index,solution=budget_only
        draw_solution_paths(problem,solution,'Maximum reward (flight budgets only; communication unrestricted)',
                            out/'paths-max-reward-budget-only.png')
        metadata['representatives']['max-reward-budget-only']={
            'source_pool':pool,'source_index':index,'reward':solution['reward'],
            'mean_time_seconds':solution['objectives'][1],
            'peak_staleness_seconds':solution.get('peak_staleness'),
            'communication_violation_seconds':solution.get('comm_violation'),
            'flight_budgets_valid':True,'communication_bound_enforced':False,
            'path_plot':'paths-max-reward-budget-only.png'}
    for name,index in selected.items():
        solution=front[index]
        draw_solution_paths(problem,solution,labels[name],out/f'paths-{name}.png')
        metadata['representatives'][name]={'front_index':index,'reward':solution['reward'],
                                           'mean_time_seconds':solution['objectives'][1],
                                           'peak_staleness_seconds':solution.get('peak_staleness'),
                                           'path_plot':f'paths-{name}.png'}
    (out/'representative-paths.json').write_text(json.dumps(metadata,indent=2,allow_nan=False)+'\n')
    if not selected:return
    chosen=front[selected['max-reward']]
    sampled,reached=draw_solution_paths(problem,chosen,'Maximum reward',out/'paths.png')
    fig2, speed=plt.subplots(figsize=(8,4))
    for m,(_,velocities,times) in enumerate(sampled):
        # Plot components: model has axis limits, not a Euclidean speed cap.
        speed.plot(times,velocities[:,0],label=f'Agent {m+1} vx');speed.plot(times,velocities[:,1],linestyle='--',label=f'Agent {m+1} vy')
    speed.set(xlabel='Time (s)',ylabel='Velocity components (m/s)',title='Continuous piecewise acceleration trajectory');speed.grid(alpha=.2);speed.legend(fontsize=8)
    fig2.tight_layout();fig2.savefig(out/'speed.png',dpi=150);plt.close(fig2)
    save_agent_path_panels(problem, chosen['trajectories'], out/'agent-paths.png', reached)


def plot_comparison(named_results, output_path):
    fig, ax = plt.subplots(figsize=(9,6))
    for name,data in named_results:
        front=sorted(data['front'],key=lambda s:s['objectives'][1])
        ax.plot([s['objectives'][1] for s in front],[s['reward'] for s in front],marker='.',label=name,alpha=.8)
    ax.set(xlabel='Average completion time (s; minimize)',ylabel='Reward (maximize)',title='Matched-budget epsilon archive fronts');ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.tight_layout();fig.savefig(output_path,dpi=150);plt.close(fig)
