"""Controlled fixed-route spatial comparison; zero optimizer starts."""
from dataclasses import asdict
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from topcc.config import Problem,Task,MotionLimits,Config
from topcc.solution import Solution,Visit,Meeting,direct_solution
from topcc.evaluator import Evaluator
from topcc.environment import problem_to_dict
from topcc.solver import solution_to_dict
from topcc.viz_icc import plot_communication
from scripts.validate_icc import validate_solution


def save_fixture(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    p=Problem((Task('a',(2,3),10),Task('b',(6,-3),10)),(0,0),(8,0),(20,20),(MotionLimits(),)*2,((0,0),)*2,'controlled-free-rendezvous')
    c=Config(mode='team_kop_icc',comm_range=1,handshake_time=.25,recurrence_bound=5.05,waypoint_workspace=(-1,9,-4,4))
    e=Evaluator(p,True,c);base=direct_solution(p);rows=[]
    for m,task in enumerate(p.tasks):rows.append((base.routes[m][0],Visit(f'task{m}','TASK',task.position,(0,0),task.id),base.routes[m][-1]))
    originals={'no_meeting':e.evaluate(Solution(tuple(rows)))}
    for name,point,task_id in [('free',(5,0),None),('task_a',p.tasks[0].position,'a'),('task_b',p.tasks[1].position,'b')]:
        routes=[]
        for m,row in enumerate(rows):routes.append(row[:-1]+(Visit(f'meet{m}','TASK' if task_id else 'FREE',point,(0,0),task_id),row[-1]))
        originals[name]=e.evaluate(Solution(tuple(routes),meetings=(Meeting('meet0','meet1'),)))
    reference={'schema_version':2,'problem':problem_to_dict(p),'config':asdict(c),'statistics':{},'front':[]}
    variants={name:json.loads(json.dumps(solution_to_dict(s))) for name,s in originals.items()}
    reference=json.loads(json.dumps(reference))
    checks={name:validate_solution(reference,s,require_feasible=False) for name,s in variants.items()}
    assert variants['free']['feasible'] and all(not variants[name]['feasible'] for name in ('no_meeting','task_a','task_b'))
    (directory/'controlled-free-fixture.json').write_text(json.dumps({**reference,'method':'fixed states/order/assignment, spatial meeting alternatives only; no optimizer runs',
                                                                   'variants':variants,'validation':checks},indent=2)+'\n')
    plot_communication({**reference,'front':[variants['free']]},directory,prefix='controlled-free')
    return variants


if __name__=='__main__':save_fixture(ROOT/'results/step4')
