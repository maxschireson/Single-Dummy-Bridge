"""Initialize or resume the existing staged exact-auction bidder recipe."""
import argparse
import fcntl
from importlib.metadata import version, PackageNotFoundError
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.bidding_refresh import sha
from bridge_harness.bidding_loop import atomic_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',required=True,type=Path)
    a=p.parse_args(); plan=json.loads(a.plan.read_text())
    repo=Path(__file__).resolve().parents[1]; os.chdir(repo)
    root=Path(plan['out']); root.mkdir(parents=True,exist_ok=True)
    lock=(root/'launch.lock').open('a+')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    cfg=json.loads(Path(plan['config']).read_text())
    if sha(plan['parent']) != '9ee52f3baa79c837001e0cb515c61a9a179cb1bf66cd5503e46331245c014dcc':
        raise ValueError('Wrong promoted Gen5 parent')
    if sha(plan['anchor']) != 'b0dff3dfae590cbe5927b2cc0402920df7b15336c3510dc92300010cadb17de3':
        raise ValueError('Wrong original BEN anchor')
    spec=json.loads((Path(plan['play_root'])/'manifest.json').read_text())['bots']['3']
    try:
        tensorflow_version=version('tensorflow')
    except PackageNotFoundError:
        tensorflow_version=version('tensorflow-cpu')
    identity=dict(schema='clean-bidding-mix-experiment-v1',config=cfg,
        dataset_sha256=sha(plan['data']),parent_sha256=sha(plan['parent']),anchor_sha256=sha(plan['anchor']),
        source_sha256={f:sha(repo/f) for f in ['bridge_harness/bidding_refresh.py','bridge_harness/bidding_ppo.py',
            'bridge_harness/bidding_play_cache.py','scripts/run_bidding_refresh.py']},
        tensorflow=tensorflow_version,created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        parent=str(Path(plan['parent']).resolve()),anchor=str(Path(plan['anchor']).resolve()),
        data=str(Path(plan['data']).resolve()),play_root=str(Path(plan['play_root']).resolve()),
        play_spec=spec,dds_library_sha256=sha(plan['dds_library']),
        limitation='Historical v2/v3/v4b results are treated as compatible; new play uses frozen Gen3. Exact auction required.',
        retention='KL to frozen original BEN on collected observations; not replay of original BEN corpus',
        promotion='No automatic promotion; test accessed only for preselected variant')
    path=root/'manifest.json'
    if path.exists():
        old=json.loads(path.read_text()); identity['created_utc']=old['created_utc']
        if old != identity:raise ValueError('Frozen run identity changed')
    else:atomic_json(path,identity)
    audit=json.loads((Path(plan['data']).parent/'summary.json').read_text())
    if audit['dataset_sha256'] != identity['dataset_sha256']:raise ValueError('Audited data changed')
    # Copy only immutable cardplay records, never the other run's live SQLite database.
    cache=root/'play-cache';cache.mkdir(exist_ok=True)
    if not (root/'cache-seed.json').exists():
        copied=[]
        for f in sorted(Path(plan['seed_cache']).glob('*.json.gz')):
            target=cache/f.name
            if not target.exists():target.write_bytes(f.read_bytes())
            if sha(target)!=sha(f):raise ValueError('Seed cache changed')
            copied.append(dict(file=f.name,sha256=sha(f)))
        atomic_json(root/'cache-seed.json',copied)
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
             TF_CPP_MIN_LOG_LEVEL='3',TF_ENABLE_ONEDNN_OPTS='0')
    cmd=[sys.executable,'-u','scripts/bidding_refresh_pipeline.py']
    for key in ('data','parent','anchor','out','play_root','dds_library','config'):
        cmd+=['--'+key.replace('_','-'),plan[key]]
    print(json.dumps(dict(stage='launch',command=cmd,manifest_sha256=sha(path),
                          new_families=audit['new_families'],counts=audit['counts'])),flush=True)
    subprocess.run(cmd,env=env,check=True)
    print(json.dumps(dict(stage='complete',out=str(root))),flush=True)


if __name__=='__main__':main()
