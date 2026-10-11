"""Nine optimizer invocations, each subprocess hard limited to120s (<10min)."""
import json,subprocess,sys,time,platform
from pathlib import Path
from dataclasses import replace
from topcc.config import Config
from topcc.environment import load_problem_instance
from topcc.solver import run_optimization,save_result
from topcc.viz import plot_result,plot_comparison
from validate_saved import validate
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/step2'

if len(sys.argv)>1 and sys.argv[1].startswith('{'):
    item=json.loads(sys.argv[1]);problem=load_problem_instance(ROOT/'benchmarks/tsiligirides/single-30s.json')
    config=Config(max_seconds=45,max_evaluations=4000,max_iterations=60,headings=4,speed_fractions=(0,.5,1),seed=item['seed'],algorithm=item['algorithm'],disabled=tuple(item['disabled']),eps_reward=1.,eps_time=.1)
    save_result(run_optimization(problem,config),OUT/(item['name']+'.json'));raise SystemExit
OUT.mkdir(parents=True,exist_ok=True)
ledger=OUT/'ledger.json'
resume='--resume-epsilon' in sys.argv
if ledger.exists() and not resume:raise SystemExit('Existing ledger: refusing accidental campaign rerun. Only explicit --resume-epsilon permitted for steering revision.')
if resume:
    manifest=json.loads(ledger.read_text())
    if len(manifest['runs'])!=3 or any(not r.get('superseded') for r in manifest['runs']):raise SystemExit('Resume only allowed after exactly3 superseded starts.')
    cases=[{'name':'epsilon-full','seed':42,'algorithm':'movns','disabled':[]}]+[{'name':'epsilon-without-'+family,'seed':42,'algorithm':'movns','disabled':[family]} for family in ('insert','remove','replace','reorder','velocity')]+[{'name':'epsilon-lns','seed':42,'algorithm':'lns','disabled':[]}]
    manifest.update(planned_runs=10,campaign_revision='epsilon dominance resumed with7 remaining slots',eps_reward=1.,eps_time=.1)
else:
    cases=[{'name':'full-seed42','seed':42,'algorithm':'movns','disabled':[]}]+[{'name':'without-'+family,'seed':42,'algorithm':'movns','disabled':[family]} for family in ('insert','remove','replace','reorder','velocity')]+[{'name':'lns-seed42','seed':42,'algorithm':'lns','disabled':[]},{'name':'full-seed7','seed':7,'algorithm':'movns','disabled':[]},{'name':'full-seed99','seed':99,'algorithm':'movns','disabled':[]}]
    manifest={'max_runs':10,'planned_runs':len(cases),'hard_timeout_seconds':120,'optimizer_seconds':45,'max_evaluations':4000,'platform':platform.platform(),'python':sys.version,'runs':[]}
manifest['source_revision']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
manifest['source_note']='Working tree includes epsilon archive steering patch and experimental tools.'
import hashlib
manifest['code_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'src').glob('*.py'))}
manifest['source_dirty']=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True))
from importlib.metadata import version
manifest['dependencies']={p:version(p) for p in ('numpy','scipy','matplotlib','pytest')}
ledger.write_text(json.dumps(manifest,indent=2)+'\n');named=[]
for case in cases:
    if len(manifest['runs'])>=10:raise SystemExit('Ten-run cap reached')
    record={**case,'archive_policy':'epsilon','eps_reward':1.,'eps_time':.1,'status':'started','started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())};manifest['runs'].append(record);ledger.write_text(json.dumps(manifest,indent=2)+'\n');start=time.monotonic()
    try:
        process=subprocess.run([sys.executable,__file__,json.dumps(case)],cwd=ROOT,timeout=120,capture_output=True,text=True)
        record.update(status='completed' if process.returncode==0 else 'failed',returncode=process.returncode,stderr=process.stderr)
    except subprocess.TimeoutExpired:record['status']='timeout'
    record['wall_seconds']=time.monotonic()-start
    ledger.write_text(json.dumps(manifest,indent=2)+'\n')
    if record['status']=='completed':
        data=json.loads((OUT/(case['name']+'.json')).read_text());record['validation']=validate(data);record['max_reward']=max(s['reward'] for s in data['front']);record['front_size']=len(data['front']);record['evaluations']=data['statistics']['evaluated'];named.append((case['name'],data));plot_result(data,OUT/case['name'])
    ledger.write_text(json.dumps(manifest,indent=2)+'\n');print(case['name'],record['status'],record['wall_seconds'],flush=True)
plot_comparison(named,OUT/'comparison.png')
