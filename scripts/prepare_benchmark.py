"""Explicit OP coordinate/reward reuse; NOT an original KOP benchmark."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
folder=root/'benchmarks/tsiligirides'
raw=(folder/'op2-budget30.txt').read_text().splitlines()
nodes=[list(map(float,line.split())) for line in raw[1:]]
data={'schema_version':1,'budget_unit':'seconds','name':'tsiligirides-op2-derived-kop-30s','start':nodes[0][:2],'end':nodes[1][:2],'tasks':[{'id':str(i+3),'position':n[:2],'reward':n[2]} for i,n in enumerate(nodes[2:])],'agents':[{'time_budget':30,'velocity_axis_limit':[3,3],'acceleration_axis_limit':[1.5,1.5],'initial_velocity':[0,0]}]}
(folder/'single-30s.json').write_text(json.dumps(data,indent=2)+'\n')
provenance={'retrieved':'2026-10-11','primary_catalog':'https://www.mech.kuleuven.be/en/mim/op','download':'https://www.mech.kuleuven.be/en/mim/op/instances/TsiligiridesOP2','original':'Tsiligirides T. Heuristic Methods Applied to Orienteering. JORS 35(9),797–809 (1984).','archive_sha256':hashlib.sha256((folder/'op2-original.zip').read_bytes()).hexdigest(),'raw_sha256':hashlib.sha256((folder/'op2-budget30.txt').read_bytes()).hexdigest(),'conversion':'All 19 tasks, unmodified coordinates/rewards. Coordinates interpreted as meters. Original 30-unit travel budget is NOT converted mathematically: new 30-second flight budget chosen for acceleration-aware experiments. Axis speed 3m/s, acceleration 1.5m/s²; zero endpoint velocities. No obstacles, collisions, or communication. Published OP optimal values do not apply.','license':'Primary download has no explicit license notice. Preserve attribution; no new license asserted for original benchmark data.'}
(folder/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
