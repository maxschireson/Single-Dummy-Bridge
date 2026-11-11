"""Freeze the unplayed Gen5 corpus as a distinct Gen5R campaign after draining."""
import argparse
import fcntl
import json
from pathlib import Path
import shutil
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load,save
from bridge_harness.gen5r import load_plan,make_bots,LABELS
from bridge_harness.loop_registry import sha,source_hash
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest

def prepare(root, source):
    root,source=Path(root).resolve(),Path(source).resolve()
    if root.exists():raise ValueError('Refusing to overwrite a frozen run')
    if not all((source/n).exists() for n in ('STOP','WATCHDOG_STOP')):
        raise ValueError('Drain the source collector and disable its recovery first')
    with (source/'.writer.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if list((source/'failures').glob('*.json')):raise ValueError('Inspect preserved source failures first')
        old=json.loads((source/'manifest.json').read_text());plan=load_plan()
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
        m=dict(schema='gen5-arena-manifest-v1',generation=5,variant='5R',campaign='gen5r-20261110',
            target=len(keep),seed=plan['seed'],roster=plan['roster'],bots=bots,
            pair_weights=plan['pair_weights'],pair_schedule=[p for p,n in plan['pair_weights'].items() for _ in range(n)],
            audit_references={'5R32':'3','5R192':'3'},common_bidder='5R32',
            corpus='corpus.jsonl',corpus_sha256=sha(root/'corpus.jsonl'),source_sha256=source_hash(),
            runtime_sha256={name:sha(ROOT/name) for name in ('ops/gen5_runtime.py','ops/prepare_gen5r.py')},
            audit=old['audit'],ben_audit=old['ben_audit'],bidding_conditions=old['bidding_conditions'],
            created_epoch=time.time(),source_generation=old['identity'],source_completed=len(done),
            source_indices='source-indices.json',source_indices_sha256=sha(root/'source-indices.json'),
            labels=LABELS,order=plan['roster'],
            interpretation='Gen5R retains all three Gen5 networks. With 10–13 tricks remaining, draw four times the nominal DDS budget, cluster shape/honor features and fit nonnegative weights to exact constrained belief moments. The DDS budget is a ceiling; fewer clusters can survive. Smaller positions retain random sampling. Allocation: 40% vs 4b, 20% vs 3, 15% vs 2, 5% vs 1, 5% vs BEN, 7.5% R32 vs R192, 7.5% R32 vs original 5-32. Common and native bidding remain separate. Remaining unplayed source deals only; old results keep their identities.')
        m['identity']=digest(m);atomic_json(root/'manifest.json',m)
        atomic_json(root/'state.json',dict(manifest_identity=m['identity'],completed=0,target=len(keep),by_pair={},root_games=0,tables=0,epoch=time.time()))
        atomic_json(root/'heartbeat.json',dict(epoch=time.time(),completed=0,workers=4,ben_workers=1,in_flight=[]))
        verify_generation(root,m)
        return m

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    m=prepare(a.run,a.source);print(json.dumps(dict(identity=m['identity'],target=m['target'],allocation=m['pair_weights'])))
