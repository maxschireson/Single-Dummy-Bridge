"""Run clean-data extraction and the predeclared scalar capacity comparison."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--normalized',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--gen4',type=Path,required=True)
    p.add_argument('--previous-families',type=Path,required=True)
    p.add_argument('--wait-for-freeze-log',type=Path)
    a=p.parse_args();a.out.mkdir(exist_ok=True,parents=True)
    if a.wait_for_freeze_log:
        started=time.monotonic()
        while True:
            log=a.wait_for_freeze_log.read_text() if a.wait_for_freeze_log.exists() else ''
            if '"stage": "complete"' in log:break
            if 'Traceback (most recent call last)' in log:
                raise RuntimeError('Data freeze failed; see '+str(a.wait_for_freeze_log))
            if time.monotonic()-started>7200:raise TimeoutError('Data freeze did not complete')
            time.sleep(5)
    parent=ROOT/'models/cardplay/gen3-2026-11-09/restored/auction-policy.npz'
    def run(stage,args):
        print(json.dumps(dict(stage=stage,event='start',epoch=time.time())),flush=True)
        with (a.out/(stage+'.log')).open('w') as log:
            subprocess.run([sys.executable,*args],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        print(json.dumps(dict(stage=stage,event='complete',epoch=time.time())),flush=True)
    data=a.out/'data'
    if not (data/'dataset.json').exists():
        run('prepare',['scripts/prepare_outcome_policy.py','--run',str(a.normalized),'--out',str(data),
            '--gen3',str(parent),'--gen4',str(a.gen4)])
    for mode in ('baseline','wide','attention'):
        fit=a.out/mode
        if not (fit/'result.json').exists():
            run(mode,['scripts/train_clean_policy_v5.py','--data',str(data),'--out',str(fit),
                '--parent',str(parent),'--rank-candidate',str(parent),
                '--previous-families',str(a.previous_families),'--mode',mode,'--epochs','8'])
    results={mode:json.loads((a.out/mode/'result.json').read_text()) for mode in ('baseline','wide','attention')}
    chosen=min(results,key=lambda mode:results[mode]['validation']['new_mse'])
    summary=dict(selected_by_validation_mse=chosen,models=results,promoted=False,
        comparison='Predeclared three architectures; same clean data, objective and epoch budget. Test is descriptive, not used to select architecture.')
    (a.out/'comparison.json').write_text(json.dumps(summary,indent=2))

if __name__=='__main__':main()
