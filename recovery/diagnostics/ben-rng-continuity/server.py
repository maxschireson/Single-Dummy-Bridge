"""Diagnostic only: checkpoint Python RNG without reseeding or changing claim logic."""
import os,sys,runpy,json,random
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
import claim
state=Path(os.environ['CLAIM_STATE'])
def tuples(x):return tuple(map(tuples,x)) if isinstance(x,list) else x
if state.exists():random.setstate(tuples(json.loads(state.read_text())))
else:state.write_text(json.dumps(random.getstate()))
Path(os.environ['CLAIM_START']).write_text(json.dumps(random.getstate()))
original=claim.Claimer.claimcheck
def traced(self,*args,**kwargs):
 result=original(self,*args,**kwargs)
 temp=state.with_suffix('.tmp');temp.write_text(json.dumps(random.getstate()));temp.replace(state)
 return result
claim.Claimer.claimcheck=traced
runpy.run_path('src/gameapi.py',run_name='__main__')
