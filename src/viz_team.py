"""Portable plots from saved full-trajectory JSON (headless by default)."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def plot_result(data, directory, prefix="full"):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    front=data["front"];problem=data["problem"]
    fig,ax=plt.subplots();ordered=sorted(front,key=lambda s:s["objectives"][1])
    ax.plot([s["objectives"][1] for s in ordered],[s["reward"] for s in ordered],"o-")
    ax.set(xlabel="Mean completion time (s), minimize",ylabel="Unique team reward, maximize",title="Team KOP epsilon archive");ax.grid(alpha=.3)
    fig.savefig(directory/f"{prefix}-pareto.png",dpi=160,bbox_inches="tight");plt.close(fig)
    representative=max(front,key=lambda s:(s["reward"],-s["objectives"][1]))
    fig,axes=plt.subplots(1,2,figsize=(12,5));path,vel=axes
    for task in problem["tasks"]:
        x,y=task["position"];path.scatter(x,y,c="gray",s=20);path.annotate(task["id"],(x,y),fontsize=7)
    horizon=max(representative["completion_times"])
    for m,tr in enumerate(representative["trajectories"]):
        times=[];positions=[];speeds=[]
        for piece in tr["pieces"]:
            local=np.linspace(0,piece["duration"],max(3,int(piece["duration"]*25)))
            p=np.asarray(piece["position"]);v=np.asarray(piece["velocity"]);a=np.asarray(piece["acceleration"])
            times.extend(piece["start_time"]+local);positions.extend(p+local[:,None]*v+.5*local[:,None]**2*a);speeds.extend(np.linalg.norm(v+local[:,None]*a,axis=1))
        if not positions:
            positions=[tr["start"]["position"]];times=[0.];speeds=[float(np.linalg.norm(tr["start"]["velocity"]))]
        positions=np.asarray(positions);line=path.plot(positions[:,0],positions[:,1],label=f"Agent {m+1}")[0]
        vel.plot(times,speeds,color=line.get_color(),label=f"Agent {m+1}")
        arrival=tr["completion_time"];vel.plot([arrival,horizon],[0,0],linestyle="--",color=line.get_color());vel.axvline(arrival,color=line.get_color(),alpha=.3)
    path.scatter(*problem["start"],marker="s",s=80,c="black",label="Start");path.scatter(*problem["end"],marker="*",s=130,c="black",label="End")
    path.set(xlabel="x (m)",ylabel="y (m)",title=f"Maximum-reward solution: {representative['reward']:g}");path.set_aspect("equal",adjustable="datalim");path.legend()
    vel.set(xlabel="Mission time (s)",ylabel="Speed magnitude (m/s)",title="Speed; dashed = free post-arrival presence");vel.legend();vel.grid(alpha=.3)
    fig.tight_layout();fig.savefig(directory/f"{prefix}-paths-speed.png",dpi=160);plt.close(fig)
    return representative

def plot_comparison(results,destination):
    fig,ax=plt.subplots(figsize=(9,6))
    for name,data in results.items():
        ordered=sorted(data["front"],key=lambda s:s["objectives"][1]);ax.plot([s["objectives"][1] for s in ordered],[s["reward"] for s in ordered],"o-",markersize=3,label=name)
    ax.set(xlabel="Mean completion time (s), minimize",ylabel="Unique team reward, maximize",title="One-neighborhood-at-a-time ablation (seed 42)");ax.legend(fontsize=8);ax.grid(alpha=.3);fig.savefig(destination,dpi=160,bbox_inches="tight");plt.close(fig)
