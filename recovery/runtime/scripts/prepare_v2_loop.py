#!/usr/bin/env python3
"""Bind both published nets and a net-only BEN bidder; prepare a resumable loop."""
import argparse
import configparser
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.improvement import initialize, writer_lock
from bridge_harness.loop_registry import sha
from bridge_harness.selfplay import atomic_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'belief', 'policy', 'ben-dir', 'ben-python', 'bid-config', 'play-config'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--exclude', type=Path, action='append', default=[])
    p.add_argument('--resource-lock', action='append', default=[])
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--port', type=int, default=8131)
    p.add_argument('--seed', type=int, default=2026110820)
    p.add_argument('--verified-ben', action='store_true', help='Pinned server has passed a live card-play smoke check')
    a = p.parse_args()
    a.root=a.root.resolve(); ben=a.ben_dir.resolve()
    with writer_lock(a.root):
        if (a.root/'campaign.json').exists(): raise ValueError('Campaign already initialized; use improvement run to resume')
        inputs=a.root/'inputs'; inputs.mkdir(exist_ok=True)
        for key in ('belief','policy','bid_config','play_config'):
            src=getattr(a,key).resolve(); dst=inputs/(key+src.suffix)
            shutil.copyfile(src,dst); setattr(a,key,dst)
        bidder=configparser.ConfigParser(); bidder.read(a.bid_config)
        if bidder.get('bidding','search_threshold')!='-1' or bidder.getboolean('bidding','check_final_contract'):
            raise ValueError('BEN bidding must be neural-only with contract rescue disabled')
        play=configparser.ConfigParser(); play.read(a.play_config)
        if play.getboolean('cardplay','play_nn_only'): raise ValueError('Reference must retain BEN card-play search')
        # This server only receives frozen auctions, but also disable its bidding
        # search so every BEN invocation in this campaign has the requested mode.
        play.set('bidding','search_threshold','-1'); play.set('bidding','check_final_contract','False')
        with a.play_config.open('w') as f: play.write(f)
        models={}
        for config in (bidder,play):
            for section in config.sections():
                for _,value in config.items(section):
                    if value.startswith('models/'):
                        path=(ben/value).resolve(); models[str(path)]=sha(path)
        atomic_json(inputs/'models.json',models)
        exclusions=set()
        for path in a.exclude: exclusions.update(json.loads(path.read_text())['deal_ids'])
        atomic_json(inputs/'exclusions.json',dict(deal_ids=sorted(exclusions)))
        s=json.loads((ROOT/'configs/self_improvement.json').read_text())
        s.update(campaign_id=a.root.name,seed=a.seed,workers=a.workers,
                 exclusion_files=[str(inputs/'exclusions.json')])
        s['bots']['v2']['artifacts']=dict(belief=str(a.belief),policy=str(a.policy))
        reference=s['bots']['ben']
        reference['kwargs']['url']=f'http://127.0.0.1:{a.port}'
        reference['artifacts']=dict(config=str(a.play_config),models_manifest=str(inputs/'models.json'))
        reference['external'].update(revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ben,text=True).strip(),
                                     operator_verified=a.verified_ben)
        s['managed_ben']=dict(python=str(a.ben_python.absolute()),ben_dir=str(ben),config=str(a.play_config),
                              port=a.port,resource_locks=a.resource_lock)
        s['corpus_command']=[str(a.ben_python.absolute()),'scripts/loop_collect_auctions.py',
            '--ben-dir',str(ben),'--config',str(a.bid_config),'--input-corpus','{input}',
            '--out','{output}','--count','{count}']
        s['trainer_command']=[str(a.ben_python.absolute()),'scripts/loop_train_combined.py',
                               '--request','{request}','--epochs','8','--patience','2','--threads','4']
        s['pinned_files']=[str(x) for x in sorted((ben/'src').rglob('*.py'))]
        s['pinned_files'] += list(models)+[str(a.bid_config),str(a.play_config)]
        atomic_json(inputs/'launch.json',s)
        initialize(a.root,s)
        print(json.dumps(dict(root=str(a.root),excluded_deals=len(exclusions),models=len(models),prepared=True)))


if __name__=='__main__':main()
