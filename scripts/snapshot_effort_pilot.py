"""Durable pilot state plus its new data and policy train/development dependencies."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.snapshot_belief_lab import archive

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();root=a.run.resolve();plan=json.loads((root/'plan.json').read_text())
    paths=[p for p in root.rglob('*') if p.is_file() and p.suffix not in ('.lock','.tmp') and 'checkpoints' not in p.parts];overrides={}
    for s in root.rglob('state.json'):
        for attempt in range(4):
            raw=s.read_bytes();state=json.loads(raw);prefix=Path(state['checkpoint']);needed=list(prefix.parent.glob(prefix.name+'.*'))
            try:captured={p.resolve():p.read_bytes() for p in needed}
            except FileNotFoundError:continue
            if len(needed)>=2 and raw==s.read_bytes():
                captured[s.resolve()]=raw;overrides.update(captured);paths.extend(needed);break
        else:raise RuntimeError('Active checkpoint changed during capture; retry')
    base=Path(plan['policy_base']);ds=json.loads((base/'dataset.json').read_text());paths.extend([base/'dataset.json',base/'families.json',Path(plan['policy_parent'])])
    paths.extend(base/e['file'] for e in ds['shards'] if e['kind']=='outcomes' and e['split'] in ('train','validation'))
    a.out.mkdir(parents=True,exist_ok=True)
    archive(a.out/'Effort_Data_Pilot_2026-11-10.zip',paths,dict(source_branch='research/belief-lab-20261110',run=str(root),python='/workspace/scratch/bf0fa8ac2d09/.venv/bin/python',
        restore='Restore only missing files to original absolute paths. Belief frozen base data and original baseline dependencies come from Belief_Lab_Frozen_Data_2026-11-10.zip and Belief_Lab_Recovery_2026-11-10.zip. Pilot policy train/development shards included; test shards deliberately excluded. Exact state refers to included optimizer checkpoints. Run scripts/run_effort_pilot.py in a live exec session only when supervisor/writer locks are free.',deadline=plan['deadline_utc']),overrides)

if __name__=='__main__':main()
