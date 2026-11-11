"""Drain and archive the early Gen6 cohort; assign only unplayed boards to medium vs BEN."""
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
from bridge_harness.loop_registry import sha
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest


def prepare(root,source):
    root,source=Path(root).resolve(),Path(source).resolve()
    if root.exists():raise ValueError('Refusing to overwrite a frozen run')
    if not all((source/n).exists() for n in ('STOP','WATCHDOG_STOP')):raise ValueError('Drain source and disable its watchdog first')
    with (source/'.writer.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        old=json.loads((source/'manifest.json').read_text());verify_generation(source,old)
        if old.get('variant')!='6' or '6-32~ben' not in old['pair_weights']:raise ValueError('Expected early Gen6 fast-BEN cohort')
        if list((source/'failures').glob('*.json')):raise ValueError('Inspect preserved failures first')
        boards=list(load(source/old['corpus']));done=set()
        if len(list((source/'episodes').glob('*.json.gz')))!=len(list((source/'receipts').glob('*.json'))):raise ValueError('Incomplete source records')
        for p in (source/'receipts').glob('*.json'):
            r=json.loads(p.read_text());i=r['index']
            if i in done or not 0<=i<len(boards) or r['manifest_identity']!=old['identity']:raise ValueError('Changed receipt identity')
            if r['family']!=deal_key(boards[i].hands,True) or r['episode_sha256']!=sha(source/'episodes'/f'{i:06d}.json.gz'):raise ValueError('Source receipt/episode mismatch')
            done.add(i)
        keep=[i for i in range(old['target']) if i not in done]
        if not keep:raise ValueError('No unplayed boards')
        m=deepcopy(old);m.pop('identity')
        m['pair_weights']={('6-256~ben' if p=='6-32~ben' else p):n for p,n in old['pair_weights'].items()}
        m['pair_schedule']=[p for p,n in m['pair_weights'].items() for _ in range(n)]
        m['audit_references']['6-256']='3'
        m.update(target=len(keep),campaign='gen6-independent-medium-ben-20261111',title='Gen 6 · independent collector',
                 created_epoch=time.time(),source_generation=old['identity'],source_completed=len(done),
                 source_indices='source-indices.json',runtime_sha256=dict(old['runtime_sha256'],**{'ops/retarget_gen6_ben.py':sha(ROOT/'ops/retarget_gen6_ben.py')}))
        m['model_note']=old['model_note']+' Corrected BEN matchup: Gen6 medium (256) vs BEN (16), 15%; all other matchups unchanged.'
        m['interpretation']=old['interpretation']+' Early cohort archived and excluded from dashboard; only its unplayed families continue here.'
        root.mkdir(parents=True)
        for folder in ('artifacts','assets'):shutil.copytree(source/folder,root/folder)
        for folder in ('episodes','receipts','failures'):(root/folder).mkdir()
        save([boards[i] for i in keep],root/'corpus.jsonl');atomic_json(root/'source-indices.json',keep)
        m.update(corpus_sha256=sha(root/'corpus.jsonl'),source_indices_sha256=sha(root/'source-indices.json'))
        m['identity']=digest(m);atomic_json(root/'manifest.json',m)
        atomic_json(root/'state.json',dict(manifest_identity=m['identity'],completed=0,target=len(keep),by_pair={},root_games=0,tables=0,epoch=time.time()))
        atomic_json(root/'heartbeat.json',dict(epoch=time.time(),completed=0,workers=4,ben_workers=1,in_flight=[]))
        verify_generation(root,m)
        return m


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--source',type=Path,required=True);a=p.parse_args()
    print(json.dumps(prepare(a.run,a.source)))
