"""Freeze the remaining Gen5R deals with the zero-margin policy ablation."""
import argparse
from copy import deepcopy
import fcntl
import json
from pathlib import Path
import shutil
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load,save
PAIR_WEIGHTS={'5RZ32~5R32':111,'5R32~5-32':74,'5R32~4b':80,'5R32~3':40,'5R32~2':30,'5R32~1':10,'5R192~ben':10,'5R32~5R192':15}
LABELS={'5RZ32':'Gen 5RZ (32)','5R32':'Gen 5R (32)','5R192':'Gen 5R (192)','5-32':'Gen 5 (32)','4b':'Gen 4b','3':'Gen 3','2':'Gen 2','1':'Gen 1','ben':'BEN (16)'}
from bridge_harness.loop_registry import sha,source_hash
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest

def load_plan(path=None):
    plan=json.loads(Path(path or ROOT/'configs/round5rz.json').read_text())
    if plan['pair_weights']!=PAIR_WEIGHTS or set(plan['roster'])!=set(LABELS):raise ValueError('Incorrect RZ allocation')
    if plan['common_bidder']!='5R32' or plan['policy_ties_only']!={'actor':'5RZ32','near_tie':0.,'samples':32}:raise ValueError('RZ must use 32 and zero near-tie margin')
    if (plan['ben']['bidding'],plan['ben']['opening_lead_samples'],plan['ben']['play_samples'])!=('neural-only',16,16):raise ValueError('BEN settings changed')
    return plan

def make_bots(old,plan):
    bots=deepcopy(old['bots'])
    if set(bots)!=set(LABELS)-{'5RZ32'}:raise ValueError('Expected the frozen Gen5R roster')
    z=deepcopy(bots['5R32']);z.pop('identity');z.update(id='5RZ32',near_tie=0.,policy_role='pimc-ties-only')
    if z['samples']!=32 or not z.get('layout_reduction'):raise ValueError('Expected 32-sample representative sampler')
    z['identity']=digest(z);bots['5RZ32']=z
    return bots


def prepare(root, source):
    root,source=Path(root).resolve(),Path(source).resolve()
    if root.exists():raise ValueError('Refusing to overwrite a frozen run')
    if not all((source/n).exists() for n in ('STOP','WATCHDOG_STOP')):
        raise ValueError('Drain the source collector and disable its recovery first')
    with (source/'.writer.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if list((source/'failures').glob('*.json')):raise ValueError('Inspect preserved source failures first')
        old=json.loads((source/'manifest.json').read_text());plan=load_plan();verify_generation(source,old)
        if old.get('variant')!='5R':raise ValueError('Expected the existing Gen5R cohort')
        if digest({k:v for k,v in old.items() if k!='identity'}) != old['identity']:
            raise ValueError('Source manifest changed')
        if sha(source/old['corpus']) != old['corpus_sha256']:raise ValueError('Source corpus changed')
        boards=list(load(source/old['corpus']));done=set()
        episodes=list((source/'episodes').glob('*.json.gz'))
        receipts=list((source/'receipts').glob('*.json'))
        if len(episodes)!=len(receipts):raise ValueError('Source episodes/receipts incomplete')
        for path in receipts:
            r=json.loads(path.read_text());i=r['index']
            if i in done or not 0<=i<len(boards) or r['manifest_identity']!=old['identity']:
                raise ValueError('Wrong source receipt identity')
            if r['family']!=deal_key(boards[i].hands,True) or r['episode_sha256']!=sha(source/'episodes'/f'{i:06d}.json.gz'):
                raise ValueError('Source receipt/episode mismatch')
            done.add(i)
        keep=[i for i in range(old['target']) if i not in done]
        if not keep:raise ValueError('No unplayed Gen5 deals remain')
        bots=make_bots(old,plan)
        for spec in bots.values():
            if digest({k:v for k,v in spec.items() if k!='identity'})!=spec['identity']:
                raise ValueError('Source bot identity changed')
            for key,expected in spec['artifact_sha256'].items():
                if sha(source/spec[key])!=expected:raise ValueError('Source artifact changed')
        root.mkdir(parents=True)
        for folder in ('artifacts','assets'):shutil.copytree(source/folder,root/folder)
        for folder in ('episodes','receipts','failures'): (root/folder).mkdir()
        save([boards[i] for i in keep],root/'corpus.jsonl')
        atomic_json(root/'source-indices.json',keep)
        m=dict(schema='gen5-arena-manifest-v1',generation=5,variant='5RZ',campaign='gen5rz-20261110',title='Gen 5R / 5RZ · current mix',
            target=len(keep),seed=plan['seed'],roster=plan['roster'],bots=bots,
            pair_weights=plan['pair_weights'],pair_schedule=[p for p,n in plan['pair_weights'].items() for _ in range(n)],
            audit_references={'5RZ32':'3','5R32':'3','5R192':'3'},common_bidder='5R32',
            corpus='corpus.jsonl',corpus_sha256=sha(root/'corpus.jsonl'),source_sha256=source_hash(),
            runtime_sha256={name:sha(ROOT/name) for name in ('ops/gen5_runtime.py','ops/prepare_gen5rz.py')},
            audit=old['audit'],ben_audit=old['ben_audit'],bidding_conditions=old['bidding_conditions'],
            created_epoch=time.time(),source_generation=old['identity'],source_completed=len(done),
            source_indices='source-indices.json',source_indices_sha256=sha(root/'source-indices.json'),
            labels=LABELS,order=plan['roster'],
            model_note='5RZ is 5R at 32 samples with zero near-tie margin: the policy only selects among equal PIMC winners (floating-point tolerance only). All networks, belief sampling, representative weighting and bidding are identical. Original 5R/5 remain unchanged.',
            interpretation='New allocation: 30% 5RZ32 vs 5R32; 20% 5R32 vs Gen5 (32). Remaining 50% follows the previous ratios: 80/370 vs 4b, 40/370 vs 3, 30/370 vs 2, 10/370 vs 1, 10/370 5R192 vs BEN (16), 15/370 5R32 vs 5R192. Exact shuffled blocks of 370 deals. Common and native auctions are separate; identical auctions reuse physical games. Completed source deals remain unchanged; only unplayed source deals are allocated. Earlier compatible 5R results remain in the current report.')
        m['identity']=digest(m);atomic_json(root/'manifest.json',m)
        atomic_json(root/'state.json',dict(manifest_identity=m['identity'],completed=0,target=len(keep),by_pair={},root_games=0,tables=0,epoch=time.time()))
        atomic_json(root/'heartbeat.json',dict(epoch=time.time(),completed=0,workers=4,ben_workers=1,in_flight=[]))
        verify_generation(root,m)
        return m

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    m=prepare(a.run,a.source);print(json.dumps(dict(identity=m['identity'],target=m['target'],allocation=m['pair_weights'])))
