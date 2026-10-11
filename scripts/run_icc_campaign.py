"""Ten bounded stage-4 searches: Tc sweep, new-family ablations, task-only control.

Every start is persisted before launch. No automatic retries or silent ledger
overwrite. Fixtures/unit checks are separate from these experimental runs.
"""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.validate_icc import validate

PROTOCOL=[
    ('tc2-seed42',2,42,[],3),('tc5-seed42',5,42,[],3),('tc10-seed42',10,42,[],3),
    ('tc5-seed7',5,7,[],3),
    *[(f'without-{family}',5,42,[family],3) for family in ('wait','meeting','free_move','free_remove')],
    ('task-only-seed42',5,42,[],0),('task-only-seed7',5,7,[],0),
]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',default=str(ROOT/'experiments/icc'))
    args=parser.parse_args();out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True);ledger=out/'ledger.json'
    if ledger.exists():raise SystemExit('Existing ledger; refusing another campaign start')
    manifest={'schema_version':1,'maximum_starts':10,'soft_seconds':45,'hard_seconds':120,'max_evaluations':2000,
              'Tc_values':[2,5,10],'source_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'platform':platform.platform(),'python':sys.version,'dependencies':{p:version(p) for p in ('numpy','scipy','matplotlib','pytest')},
              'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'src').glob('*.py'))},
              'instance_sha256':hashlib.sha256((ROOT/'benchmarks/tsiligirides/icc-20s.json').read_bytes()).hexdigest(),
              'runs':[]}
    for label,tc,seed,disabled,cap in PROTOCOL:
        assert len(manifest['runs'])<10
        output=out/f'{label}.json'
        command=[sys.executable,'-m','topcc.main','--instance',str(ROOT/'benchmarks/tsiligirides/icc-20s.json'),
                 '--mode','team_kop_icc','--recurrence-bound',str(tc),'--comm-range','2','--handshake-time','.5',
                 '--max-free-waypoints',str(cap),'--seed',str(seed),'--max-seconds','45','--max-evaluations','2000',
                 '--max-iterations','80','--eps-reward','1','--eps-time','.1','--output',str(output)]
        if disabled:command+=['--disable',*disabled]
        record={'label':label,'Tc':tc,'seed':seed,'disabled':disabled,'free_cap':cap,'status':'started','command':command,
                'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
        manifest['runs'].append(record);ledger.write_text(json.dumps(manifest,indent=2)+'\n')
        started=time.perf_counter()
        try:
            process=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=120)
            record['wall_seconds']=time.perf_counter()-started;record['returncode']=process.returncode
            (out/f'{label}.log').write_text(process.stdout+process.stderr)
            if process.returncode!=0:raise RuntimeError(f'Optimizer failed: {process.stderr}')
            data=json.loads(output.read_text())
            if not data['front']:raise RuntimeError('No communication-feasible front found')
            check_start=time.perf_counter();checks=validate(data,include_bank=True)
            record.update(status='validated',validation=checks,validation_seconds=time.perf_counter()-check_start,
                          evaluations=data['statistics']['evaluated'],elapsed_seconds=data['elapsed_seconds'],
                          max_reward=max(s['reward'] for s in data['front']),front_size=len(data['front']),
                          free_front_solutions=sum(any(v['kind']=='FREE' for r in s['routes'] for v in r) for s in data['front']),
                          working_pool_size=len(data['working_pool']),unresolved=data['statistics'].get('unresolved',0),
                          sha256=hashlib.sha256(output.read_bytes()).hexdigest())
            print(label,'validated',record['max_reward'],'reward',record['wall_seconds'],'s',flush=True)
        except Exception as exc:
            record.update(status='failed',error=str(exc),wall_seconds=time.perf_counter()-started)
            raise
        finally:ledger.write_text(json.dumps(manifest,indent=2)+'\n')
    print('All ten searches and independent front/bank validations completed.',flush=True)


if __name__=='__main__':main()
