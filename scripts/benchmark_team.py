"""Nine bounded optimizer runs; ledger records starts before subprocess execution."""
import json,sys,subprocess,hashlib,time
from importlib.metadata import version
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.validate_team import validate
from scripts.plot_saved_stage_results import plot_stage
from topcc.viz_team import plot_result,plot_comparison
ROOT=Path(__file__).resolve().parents[1]

def main():
    out=ROOT/'results/step3';out.mkdir(parents=True,exist_ok=True);ledger=out/'ledger.json'
    if ledger.exists():raise SystemExit('Ledger exists; refusing duplicate experiment starts')
    protocol=[('full',42,[]),*[(f'without-{n}',42,[n]) for n in ('insert','remove','replace','reorder','velocity','assignment')],('full-seed7',7,[]),('full-seed99',99,[])]
    entries=[];results={}
    prior=json.loads((out/'superseded-ledger.json').read_text()) if (out/'superseded-ledger.json').exists() else []
    assert len(prior)+len(protocol)<=10
    for label,seed,disabled in protocol:
        output=out/f'{label}.json';command=[sys.executable,'-m','topcc.main','--instance',str(ROOT/'benchmarks/tsiligirides/team-20s.json'),'--mode','team_kop','--seed',str(seed),'--max-seconds','45','--max-evaluations','4000','--max-iterations','100','--output',str(output)]
        if disabled:command.extend(['--disable',*disabled])
        entry={'label':label,'seed':seed,'disabled':disabled,'command':command,'state':'started','hard_timeout_seconds':120};entries.append(entry);ledger.write_text(json.dumps(entries,indent=2)+'\n');start=time.perf_counter()
        try:
            process=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=120);entry.update(returncode=process.returncode,wall_seconds=time.perf_counter()-start)
            (out/f'{label}.log').write_text(process.stdout+process.stderr)
            if process.returncode:raise RuntimeError(f'{label} failed: {process.stderr}')
            data=json.loads(output.read_text());assert data['front'];checks=validate(data)
            entry.update(state='validated',validation=checks,elapsed_seconds=data['elapsed_seconds'],evaluations=data['statistics']['evaluated'],front_size=len(data['front']),max_reward=max(s['reward'] for s in data['front']),sha256=hashlib.sha256(output.read_bytes()).hexdigest())
            results[label]=data
        finally:ledger.write_text(json.dumps(entries,indent=2)+'\n')
        print(label,entry['max_reward'],entry['elapsed_seconds'],flush=True)
    plot_result(results['full'],out);plot_comparison({k:v for k,v in results.items() if not k.startswith('full-seed')},out/'ablations.png')
    manifest={'protocol':'9 epsilon optimizer starts plus 1 interrupted superseded crowding start;45s soft/120s hard;4000 evaluations each','code_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'src').glob('*.py'))},'python_version':sys.version,'packages':{name:version(name) for name in ('numpy','scipy','matplotlib','pytest')},'source_sha256':hashlib.sha256((ROOT/'benchmarks/tsiligirides/op2-original.zip').read_bytes()).hexdigest(),'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name!='manifest.json'}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    plot_stage(3,ROOT)
if __name__=='__main__':main()
