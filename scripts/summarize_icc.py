"""Parse saved data, compare Tc, and regenerate plots without optimizer starts."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from topcc.viz_icc import plot_fronts,plot_communication
from matplotlib import pyplot as plt


def nondominated(solutions):
    # Exact front of this finite bank, not a globally optimal continuous front.
    by_objective={tuple(s['objectives']):s for s in solutions}
    ordered=sorted(by_objective.values(),key=lambda s:(s['objectives'][0],s['objectives'][1]))
    best=float('inf');kept=[]
    for s in ordered:
        if s['objectives'][1]<best:kept.append(s);best=s['objectives'][1]
    return sorted(kept,key=lambda s:s['objectives'][1])


def hypervolume(front,reference_time=20):
    ordered=sorted(front,key=lambda s:s['objectives'][1])
    return sum(s['reward']*((ordered[i+1]['objectives'][1] if i+1<len(ordered) else reference_time)-s['objectives'][1]) for i,s in enumerate(ordered))


def summarize(directory):
    directory=Path(directory);ledger=json.loads((directory/'ledger.json').read_text())
    completed=[r for r in ledger['runs'] if r['status']=='validated']
    results={r['label']:json.loads((directory/f"{r['label']}.json").read_text()) for r in completed}
    rows=[]
    for r in completed:
        data=results[r['label']]
        row={k:r[k] for k in ('label','Tc','seed','free_cap','evaluations','wall_seconds','max_reward','front_size','free_front_solutions','unresolved')}
        row['hypervolume']=hypervolume(data['front']);row['disabled']=' '.join(r['disabled'])
        row['max_front_delta']=max(s['peak_staleness'] for s in data['front'])
        rows.append(row)
    (directory/'summary.json').write_text(json.dumps({'schema_version':1,'rows':rows,'hypervolume_reference':[0,20],'ledger':'ledger.json'},indent=2)+'\n')
    with (directory/'summary.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    independent={f'Tc={tc}s':results[f'tc{tc}-seed42']['front'] for tc in (2,5,10)}
    plot_fronts(independent,directory/'tc-independent-fronts.png','Independent MOVNS searches: Tc sweep (epsilon fronts)')
    ablations={label:data['front'] for label,data in results.items() if label=='tc5-seed42' or label.startswith('without-') or label=='task-only-seed42'}
    plot_fronts(ablations,directory/'ablations.png','New communication-family ablations at Tc=5s, seed42')
    bank={}
    for label,data in results.items():
        for s in data['front']+data['candidate_bank']:
            indices={v['id']:(m,k) for m,r in enumerate(s['routes']) for k,v in enumerate(r)}
            pairs=sorted(tuple(sorted((indices[p['left']],indices[p['right']]))) for p in s['meetings'])
            key=json.dumps([[[v['kind'],v['position'],v['velocity'],v['task_id'],v['wait']] for v in r] for r in s['routes']]+[pairs],sort_keys=True)
            bank[key]={**s,'source_run_label':label,'source_recurrence_bound':data['config']['recurrence_bound']}
    common=[];fronts={}
    for tc in (2,5,10):
        feasible=[s for s in bank.values() if s['motion_budget_valid'] and s['validation_status']=='valid' and s['peak_staleness']<=tc]
        front=nondominated(feasible)
        front=[{**s,'original_feasibility':s['feasible'],'original_comm_violation':s['comm_violation'],
                'feasible':True,'reason':'','comm_violation':max(0.,s['peak_staleness']-tc),'evaluated_Tc':tc} for s in front]
        fronts[f'Tc={tc}s']=front
        common.append({'Tc':tc,'feasible_candidates':len(feasible),'front':front,'max_reward':max((s['reward'] for s in front),default=0),'hypervolume':hypervolume(front)})
    assert [x['feasible_candidates'] for x in common]==sorted(x['feasible_candidates'] for x in common)
    assert [x['max_reward'] for x in common]==sorted(x['max_reward'] for x in common)
    assert [x['hypervolume'] for x in common]==sorted(x['hypervolume'] for x in common)
    (directory/'tc-common-bank.json').write_text(json.dumps({'schema_version':1,'method':'exact nondominance of saved finite bank filtered by fixed Delta; no new optimization',
                                                           'candidate_count':len(bank),'sweep':common},indent=2)+'\n')
    plot_fronts(fronts,directory/'tc-common-bank-fronts.png','Same saved trajectories: Tc feasibility filtering (finite-bank exact fronts)')
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    axes[0].plot([x['Tc'] for x in common],[x['max_reward'] for x in common],'o-',label='Common bank')
    axes[0].plot([2,5,10],[max(s['reward'] for s in independent[f'Tc={tc}s']) for tc in (2,5,10)],'s--',label='Independent searches')
    axes[0].set(xlabel='Tc (s)',ylabel='Best reward');axes[0].legend();axes[0].grid(alpha=.2)
    axes[1].plot([x['Tc'] for x in common],[x['feasible_candidates'] for x in common],'o-')
    axes[1].set(xlabel='Tc (s)',ylabel='Feasible saved candidates');axes[1].grid(alpha=.2)
    fig.tight_layout();fig.savefig(directory/'tc-metrics.png',dpi=160);plt.close(fig)
    plot_communication(results['tc5-seed42'],directory,prefix='tc5')
    eligible=[(label,data) for label,data in results.items() if any(any(v['kind']=='FREE' for r in s['routes'] for v in r) for s in data['front'])]
    if eligible:
        label,data=eligible[0];free=[s for s in data['front'] if any(v['kind']=='FREE' for r in s['routes'] for v in r)]
        plot_communication({**data,'front':free},directory,prefix='free-front-example')
    lines=['# Stage 4 — intermittent communication experiments','',
           'Ten optimizer starts on all 19 authentic Tsiligirides OP2 tasks, with two new 20-second agent budgets, range 2 m, handshake 0.5 s, and componentwise velocity/acceleration limits 3 m/s and 1.5 m/s². Collisions are ignored. The archive minimizes only negative reward and mean completion time with epsilon widths 1 and 0.1 s; delta is a constraint/guide.',
           '', '| Run | Tc | Seed | Disabled | Free cap | Evaluations | Wall s | Reward | Front | Free-front points | HV |',
           '|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|']
    for x in rows:lines.append(f"| {x['label']} | {x['Tc']} | {x['seed']} | {x['disabled'] or '—'} | {x['free_cap']} | {x['evaluations']} | {x['wall_seconds']:.3f} | {x['max_reward']:g} | {x['front_size']} | {x['free_front_solutions']} | {x['hypervolume']:.3f} |")
    lines+=['','## Protocol and interpretation','',
            'Each search has a 45-second soft runtime, 2,000-evaluation/80-iteration limits, and a 120-second hard subprocess timeout. All ten starts are recorded before execution; there are no retries. Four singleton ablations remove the new wait, meeting, free_move, and free_remove families. The six inherited task/assignment families were individually tested in stages 2/3 and are retained here. Task-only controls set the free-waypoint cap to zero while retaining task-location rendezvous. Matched full/task-only seeds 42 and 7 runs provide a small sensitivity comparison, not statistical significance.',
            '', 'The independent-search Tc plot mixes changed feasibility and changed search trajectories. It need not be monotone under a finite stochastic budget. The common-bank plot instead filters exactly the same stored physically valid trajectories by their Tc-independent Delta, then computes an exact nondominated front of that finite bank; its feasible counts, best reward and hypervolume are checked monotone. Neither plot establishes the unrestricted global Pareto front.',
            '', 'Operator activity matters: inspect each run’s `statistics.operators`. The seed 42 baseline can spend its fixed evaluation budget in inherited task neighborhoods before invoking communication families; an identical ablation outcome with no baseline activity is uninformative about that family. Seed 7 exercises communication operators and provides the paired task-only comparison. A controlled independent fixture additionally isolates the geometric advantage of a free rendezvous position.',
            '', 'All recorded searches reached the same 2,000-evaluation limit before the wall deadline. None of the independently optimized archive representatives contains FREE visits on this dense instance. At seed 7, allowing free positions produced the same best reward 160 but lower hypervolume than the task-only control; no benchmark advantage is established. The fixed-state geometric fixture below has a narrower claim.',
            '', '## Controlled free-position fixture', '',
            '[Fixture JSON](../experiments/icc/controlled-free-fixture.json) fixes each agent’s task assignment/order and zero visit velocities, and compares no meeting, meetings at either existing task, and an off-task meeting at (5,0). The free meeting has Delta 5.02223 s and satisfies Tc=5.05 s; the no-meeting and task-location alternatives have Delta 5.21540 s, 6.26520 s, and 5.09363 s and fail that bound. Every variant is independently validated. This isolates a spatial feasibility improvement for these fixed routes; it does not prove all task-only assignments or trajectories infeasible.', '',
            '![Controlled free position](../experiments/icc/controlled-free-free-waypoints.png)',
            '', 'Hypervolume reference is (0,20) in minimization coordinates (-reward, mean time), shared across all comparisons. Practical wall stops can yield unequal evaluation counts. Prefix candidate limits, finite velocity menus and capped free positions are explicit algorithmic restrictions. A zero observed ablation effect does not prove a family useless.',
            '', 'Every exported front and candidate-bank solution is independently checked from saved data: motion/velocity continuity, axis bounds, budgets, declared visit states/waits, meeting overlap, incidental task union, raw/effective contacts using companion-matrix quartic roots, and Delta using reverse temporal reachability. The validator does not call production connectors, contact extraction, or propagation. Unresolved production contacts are counted/rejected, not treated as feasible. Ledger entries record checks and residuals. Independent polynomial solvers can disagree on first-visitor order for sub-tolerance simultaneous arrivals, so diagnostic attribution is checked against earliest arrival within 2e-6; union reward remains exact over the verified task set. The last saved bank was revalidated under that policy without another optimizer start, preserving its original validation error in the ledger.',
            '', '## Parseable artifacts','',
            '[Run ledger](../experiments/icc/ledger.json), [independent validation summary](../experiments/icc/validation-summary.json), [summary JSON](../experiments/icc/summary.json), [summary CSV](../experiments/icc/summary.csv), [fixed-bank sweep JSON](../experiments/icc/tc-common-bank.json), and per-run schema-version 2 JSON contain full routes, meetings, actual visit times, accelerated trajectories, raw/effective contacts, clock history, bottleneck, Delta, violation, working pool and a bounded candidate bank. Source/instance hashes and software versions are recorded; the artifact manifest hashes the files.',
            '', 'Regenerate plots and summaries without additional optimizer runs:', '', '```sh', '.venv/bin/python scripts/save_icc_fixture.py', '.venv/bin/python scripts/summarize_icc.py', '```',
            '', 'For reproduction in a fresh output directory, `scripts/run_icc_campaign.py --output-dir NEW_DIRECTORY` refuses to overwrite an existing ledger. Existing recorded outputs should not be silently replaced.',
            '', '![Independent searches](../experiments/icc/tc-independent-fronts.png)', '', '![Fixed trajectory bank](../experiments/icc/tc-common-bank-fronts.png)', '', '![Ablations](../experiments/icc/ablations.png)', '', '![Contact and staleness timeline](../experiments/icc/tc5-communication.png)', '', '![Paths and velocity](../experiments/icc/tc5-paths-speed.png)']
    (ROOT/'docs/experiments-icc.md').write_text('\n'.join(lines)+'\n')
    manifest={'schema_version':1,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.is_file() and p.name!='manifest.json'}}
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Summarized',len(rows),'runs;',len(bank),'unique saved trajectories in common-bank sweep.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',default=str(ROOT/'experiments/icc'))
    summarize(parser.parse_args().directory)
