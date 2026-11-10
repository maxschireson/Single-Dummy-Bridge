"""Bounded-process supervisor: finish all mixes, select on dev, test once."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',required=True);p.add_argument('--parent',required=True)
    p.add_argument('--anchor',required=True);p.add_argument('--out',required=True,type=Path)
    p.add_argument('--play-root',required=True);p.add_argument('--dds-library',required=True)
    p.add_argument('--config',default='configs/bidding_exact_mixes.json')
    a=p.parse_args();cfg=json.load(open(a.config));a.out.mkdir(parents=True,exist_ok=True)
    lock=(a.out/'supervisor.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    cmd=[sys.executable,'scripts/run_bidding_refresh.py','--data',a.data,'--parent',a.parent,'--anchor',a.anchor,
         '--out',str(a.out),'--play-root',a.play_root,'--dds-library',a.dds_library,'--config',a.config]
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3',TF_ENABLE_ONEDNN_OPTS='0')
    for v in cfg['variants']:
        while not (a.out/v['name']/'complete.json').exists():
            with (a.out/'pipeline.log').open('a') as log:
                staged=[sys.executable,'scripts/bidding_refresh_stage.py']+cmd[2:]
                for stage in ['collect','play','update']:
                    subprocess.run(staged+['--stage',stage,'--variant',v['name']],env=env,
                                   stdout=log,stderr=subprocess.STDOUT,check=True)
    with (a.out/'pipeline.log').open('a') as log:
        subprocess.run(cmd+['--phase','dev'],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    dev=json.load(open(a.out/'dev-summary.json'))
    def key(v):
        return (dev['play']['variants'][v['name']]['common']['mean_imps'],
                dev['dds']['variants'][v['name']]['common']['mean_imps'],v['anchor_weight'],-v['play_fraction'])
    best=max(cfg['variants'],key=key)
    selection=dict(variant=best['name'],rule='Clean-play dev IMPs, DDS IMPs, stronger retention, lower play fraction',
                   selected_epoch=time.time(),test_unopened=True)
    path=a.out/'selection.json'
    if path.exists():
        frozen=json.load(open(path))
        if frozen.get('selection_mode')=='user_initial_gen5':
            best=next(v for v in cfg['variants'] if v['name']==frozen['variant'])
        elif frozen['variant']!=selection['variant']:raise ValueError('Selection changed')
    else:path.write_text(json.dumps(selection,indent=2))
    with (a.out/'pipeline.log').open('a') as log:
        subprocess.run(cmd+['--phase','test','--variant',best['name']],env=env,
                       stdout=log,stderr=subprocess.STDOUT,check=True)
    (a.out/'pipeline-complete.json').write_text(json.dumps(dict(selected=best['name'],epoch=time.time()),indent=2))


if __name__=='__main__':main()
