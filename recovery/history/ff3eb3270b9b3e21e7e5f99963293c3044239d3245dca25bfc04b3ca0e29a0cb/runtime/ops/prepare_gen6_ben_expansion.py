"""Freeze unplayed boards after a significance-triggered BEN budget expansion."""
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
from bridge_harness.loop_registry import sha,source_hash
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest
from ops.prepare_gen6 import verify_source
from ops.prepare_ben_round5 import validate
import configparser


def build(old,profile32):
    if old.get('variant')!='6' or old['pair_weights'].get('6-256~ben')!=3:raise ValueError('Expected Gen6 medium/BEN16 allocation')
    c=configparser.ConfigParser(interpolation=None);c.read(profile32);validate(c,32)
    m=deepcopy(old);m.pop('identity');m.pop('prior_manifests',None)
    b=deepcopy(old['bots']['ben']);b.pop('identity');b.update(id='ben-32',samples=32,url='http://127.0.0.1:8088',config='assets/ben-32.conf')
    b['artifact_sha256']['config']=sha(profile32);b['identity']=digest(b);m['bots']['ben32']=b
    m['pair_weights']={p:2*n for p,n in old['pair_weights'].items() if p!='6-256~ben'}
    m['pair_weights'].update({'6-256~ben32':3,'6-32~ben':3})
    m['pair_schedule']=[p for p,n in m['pair_weights'].items() for _ in range(n)]
    m['audit_references'].update({'6-32':'3','6-256':'3'})
    m['roster']=[*old['roster'],'ben32'];m['order']=[*old['order'],'ben32'];m['labels']['ben32']='BEN (32)'
    m.update(campaign='gen6-independent-ben-expansion-20261111',title='Gen 6 · BEN budget expansion',
             source_sha256=source_hash(),runtime_sha256={n:sha(ROOT/n) for n in ('ops/gen5_runtime.py','ops/prepare_gen6_ben_expansion.py')},
             created_epoch=time.time(),source_generation=old['identity'])
    m['model_note']=old['model_note']+' After positive significance trigger, BEN16/medium receives no new boards; BEN32/medium and BEN16/fast each receive 7.5%. BEN32 uses a separately configured service.'
    return m


def prepare(root,source,profile32,trigger):
    root,source=Path(root).resolve(),Path(source).resolve()
    if root.exists():raise ValueError('Refusing to overwrite frozen run')
    if not all((source/n).exists() for n in ('STOP','WATCHDOG_STOP')):raise ValueError('Drain source and disable watchdog first')
    with (source/'.writer.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        old=json.loads((source/'manifest.json').read_text());verify_source(source,old)
        if list((source/'failures').glob('*.json')):raise ValueError('Inspect preserved failures first')
        boards=list(load(source/old['corpus']));done=set()
        if len(list((source/'episodes').glob('*.json.gz')))!=len(list((source/'receipts').glob('*.json'))):raise ValueError('Incomplete source records')
        for p in (source/'receipts').glob('*.json'):
            r=json.loads(p.read_text());i=r['index']
            if i in done or not 0<=i<len(boards) or r['manifest_identity'] not in {old['identity'],*old.get('prior_manifests',{})}:raise ValueError('Changed receipt identity')
            if r['family']!=deal_key(boards[i].hands,True) or r['episode_sha256']!=sha(source/'episodes'/f'{i:06d}.json.gz'):raise ValueError('Receipt/episode mismatch')
            done.add(i)
        keep=[i for i in range(old['target']) if i not in done]
        if not keep:raise ValueError('No unplayed boards')
        m=build(old,profile32)
        root.mkdir(parents=True)
        for folder in ('artifacts','assets'):shutil.copytree(source/folder,root/folder)
        shutil.copy2(profile32,root/'assets/ben-32.conf')
        for name in ('episodes','receipts','failures'):(root/name).mkdir()
        save([boards[i] for i in keep],root/'corpus.jsonl');atomic_json(root/'source-indices.json',keep);atomic_json(root/'significance-trigger.json',trigger)
        m.update(target=len(keep),corpus_sha256=sha(root/'corpus.jsonl'),source_completed=len(done),source_indices='source-indices.json',source_indices_sha256=sha(root/'source-indices.json'),allocation_trigger=trigger)
        m['identity']=digest(m);atomic_json(root/'manifest.json',m)
        atomic_json(root/'state.json',dict(manifest_identity=m['identity'],completed=0,target=len(keep),by_pair={},root_games=0,tables=0,epoch=time.time()))
        atomic_json(root/'heartbeat.json',dict(epoch=time.time(),completed=0,workers=4,ben_workers=1,in_flight=[]))
        verify_generation(root,m);return m
