"""Portable plots from saved full-trajectory JSON (headless by default)."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from .viz_paths import add_speed_colorbars, draw_speed_paths, draw_task_markers, save_agent_path_panels

def plot_result(data, directory, prefix="full"):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    front=data["front"];problem=data["problem"]
    fig,ax=plt.subplots();ordered=sorted(front,key=lambda s:s["objectives"][1])
    ax.plot([s["objectives"][1] for s in ordered],[s["reward"] for s in ordered],"o-")
    ax.set(xlabel="Mean completion time (s), minimize",ylabel="Unique team reward, maximize",title="Team KOP epsilon archive");ax.grid(alpha=.3)
    fig.savefig(directory/f"{prefix}-pareto.png",dpi=160,bbox_inches="tight");plt.close(fig)
    representative=max(front,key=lambda s:(s["reward"],-s["objectives"][1]))
    fig,axes=plt.subplots(1,2,figsize=(12,5));path,vel=axes
    reached=set().union(*(set(ids) for ids in representative.get("reached_tasks",[])))
    draw_task_markers(path, problem["tasks"], reached)
    for task in problem["tasks"]:
        x,y=task["position"]
        if len(problem["tasks"])<=30 or task["id"] in reached:
            path.annotate(task["id"],(x,y),fontsize=7)
    horizon=max(representative["completion_times"])
    sampled, speed_colors = draw_speed_paths(path, representative["trajectories"], samples_per_second=25)
    for m,((_, velocities, times),tr) in enumerate(zip(sampled,representative["trajectories"])):
        speeds=np.linalg.norm(velocities,axis=1)
        line=vel.plot(times,speeds,label=f"Agent {m+1}")[0]
        arrival=tr["completion_time"];vel.plot([arrival,horizon],[0,0],linestyle="--",color=line.get_color());vel.axvline(arrival,color=line.get_color(),alpha=.3)
    path.scatter(*problem["start"],marker="s",s=80,c="black",label="Start");path.scatter(*problem["end"],marker="*",s=130,c="black",label="End")
    path.set(xlabel="x (m)",ylabel="y (m)",title=f"Maximum-reward solution: {representative['reward']:g}");path.set_aspect("equal",adjustable="datalim");path.legend()
    vel.set(xlabel="Mission time (s)",ylabel="Speed magnitude (m/s)",title="Speed; dashed = free post-arrival presence");vel.legend();vel.grid(alpha=.3)
    add_speed_colorbars(fig, path, speed_colors)
    fig.savefig(directory/f"{prefix}-paths-speed.png",dpi=160);plt.close(fig)
    save_agent_path_panels(problem, representative["trajectories"],
                           directory/f"{prefix}-agent-paths.png", reached)
    return representative

def plot_comparison(results,destination):
    fig,ax=plt.subplots(figsize=(9,6))
    for name,data in results.items():
        ordered=sorted(data["front"],key=lambda s:s["objectives"][1]);ax.plot([s["objectives"][1] for s in ordered],[s["reward"] for s in ordered],"o-",markersize=3,label=name)
    ax.set(xlabel="Mean completion time (s), minimize",ylabel="Unique team reward, maximize",title="One-neighborhood-at-a-time ablation (seed 42)");ax.legend(fontsize=8);ax.grid(alpha=.3);fig.savefig(destination,dpi=160,bbox_inches="tight");plt.close(fig)
