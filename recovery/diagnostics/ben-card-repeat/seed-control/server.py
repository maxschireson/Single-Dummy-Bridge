import sys,runpy,random,json,hashlib,os
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
import claim
original=claim.Claimer.claimcheck
def traced(self,*args,**kwargs):
 random.seed(42)
 result=original(self,*args,**kwargs)
 print('DIAGNOSTIC_CLAIM',json.dumps(dict(bad_play=result,seed=42)),flush=True)
 return result
claim.Claimer.claimcheck=traced
runpy.run_path('src/gameapi.py',run_name='__main__')
