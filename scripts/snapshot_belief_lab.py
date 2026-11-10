"""Save immutable data once and current recoverable experiment state separately."""
import argparse,hashlib,json,sys,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.belief_capacity import sha

def archive(target,paths,notes):
    paths=sorted(set(Path(p).resolve() for p in paths if Path(p).is_file()));records=[]
    with zipfile.ZipFile(target.with_suffix('.tmp'),'w',zipfile.ZIP_DEFLATED,compresslevel=2) as z:
        for p in paths:
            raw=p.read_bytes();name=str(p).lstrip('/');z.writestr(name,raw);records.append(dict(path='/'+name,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
        z.writestr('RECOVERY.json',json.dumps(dict(notes=notes,files=records),indent=2))
    target.with_suffix('.tmp').replace(target)
    with zipfile.ZipFile(target) as z:
        if z.testzip() is not None:raise ValueError('Corrupt checkpoint archive')
        for r in records:
            if hashlib.sha256(z.read(r['path'].lstrip('/'))).hexdigest()!=r['sha256']:raise ValueError('Checkpoint bytes changed')
    print(json.dumps(dict(file=str(target),bytes=target.stat().st_size,sha256=sha(target),files=len(paths))),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--include-data',action='store_true');a=p.parse_args();root=a.run.resolve();a.out.mkdir(parents=True,exist_ok=True)
    plan=json.loads((root/'plan.json').read_text());data=root/'data';ds=json.loads((data/'dataset.json').read_text());dm=json.loads((data/'manifest.json').read_text())
    notes=dict(source_repository='maxschireson/Single-Dummy-Bridge',source_branch='research/belief-lab-20261110',workdir=str(root.parents[1]),run=str(root),python='/workspace/scratch/bf0fa8ac2d09/.venv/bin/python',
        restore='Archive members use original absolute paths without leading slash. Verify RECOVERY.json and restore only missing files, never overwrite newer state. Clone the source branch into workdir if absent. Recreate Python environment with numpy, scipy and tensorflow 2.21 if required. Preserve inherited family boundaries.',
        runtime_checkpoint='Optimizer, epoch cursor and dropout RNG state are atomic per fit. Resume supervisor; never duplicate a held lock.',deadline=plan['deadline_utc'])
    if a.include_data:
        paths=[data/'dataset.json',data/'manifest.json',data/'fixed/dataset.json',data/'fixed/manifest.json']+[Path(e['file']) for e in ds['shards']]
        oldm=Path(dm['base'])/'manifest.json';old=json.loads(oldm.read_text());paths.append(oldm)
        for e in dm['normalized_sources']+old['families']:
            if e['split']=='test':paths.extend(Path(s['path']) for s in e['sources'])
        archive(a.out/'Belief_Lab_Frozen_Data_2026-11-10.zip',paths,notes)
    paths=[p for p in root.rglob('*') if p.is_file() and 'data' not in p.relative_to(root).parts and p.suffix not in ('.lock','.sqlite','.tmp') and not p.name.endswith(('-wal','-shm')) and 'checkpoints' not in p.parts]
    # Retain immutable epoch exports, selected models and exact in-progress state.
    for statepath in (root/'fits').glob('*/state.json'):
        if (statepath.parent/'result.json').exists():continue
        state=json.loads(statepath.read_text());prefix=Path(state['checkpoint']);paths.extend(prefix.parent.glob(prefix.name+'.*'))
    for job in plan['jobs']:
        cfg=json.loads(Path(job['config']).read_text())
        if cfg.get('parent') and Path(cfg['parent']).exists():paths.append(Path(cfg['parent']))
    paths += [Path(plan['baseline']),Path('/workspace/scratch/8fd3c92bf5b8/timing-v4/restored-v4/partition.json'),
        Path('/workspace/scratch/63fa72341134/bridge-v5-calibration/runs/v5-ben-100/models/policy.npz'),
        Path('/workspace/scratch/bbe90ba77a68/bridge-bidding-refresh/models/bidding/gen5-2026-11-10/bidder.keras'),
        Path(__file__).resolve().parents[1]/'bridge_harness/libbridge_dds.so']
    archive(a.out/'Belief_Lab_Recovery_2026-11-10.zip',paths,notes)

if __name__=='__main__':main()
