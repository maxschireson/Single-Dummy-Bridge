"""Freeze remaining capture families under the user-authorized fast-only allocation."""
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
from ops.prepare_gen6 import verify_source,gap_fork_block


def prepare(root,source,plan_path=None):
    root,source=Path(root).resolve(),Path(source).resolve()
    if root.exists():raise ValueError('Refusing to overwrite a frozen run')
    if not all((source/n).exists() for n in ('STOP','WATCHDOG_STOP')):raise ValueError('Drain the source and disable its watchdog first')
    plan_path=Path(plan_path or ROOT/'configs/round6-fast-selfplay.json')
    plan=json.loads(plan_path.read_text())
    if plan['pair_weights']!={'6-32~6-32':37,'6-32~ben':3} or plan['roster']!=['6-32','ben']:raise ValueError('Incorrect fast-only allocation')
    with (source/'.writer.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        old=json.loads((source/'manifest.json').read_text());verify_source(source,old)
        if old.get('variant')!='6':raise ValueError('Expected Gen6 source')
        if gap_fork_block(plan)!=old.get('gap_fork'):raise ValueError('Capture settings changed')
        if old['audit']['probability']!=.5:raise ValueError('Expected unchanged 50% tie audits')
        if list((source/'failures').glob('*.json')):raise ValueError('Inspect preserved failures first')
        boards=list(load(source/old['corpus']));done=set()
        if len(list((source/'episodes').glob('*.json.gz')))!=len(list((source/'receipts').glob('*.json'))):raise ValueError('Incomplete source records')
        for p in (source/'receipts').glob('*.json'):
            r=json.loads(p.read_text());i=r['index']
            if i in done or not 0<=i<len(boards) or r['manifest_identity']!=old['identity']:raise ValueError('Changed source receipt identity')
            if r['family']!=deal_key(boards[i].hands,True) or r['episode_sha256']!=sha(source/'episodes'/f'{i:06d}.json.gz'):raise ValueError('Receipt/episode mismatch')
            done.add(i)
        keep=[i for i in range(old['target']) if i not in done]
        if not keep:raise ValueError('No unplayed source families')
        m=deepcopy(old);m.pop('identity')
        m.update(bots={k:deepcopy(old['bots'][k]) for k in ('6-32','ben','3')},roster=plan['roster'],order=plan['roster'],
            labels={k:old['labels'][k] for k in ('6-32','ben','3')},pair_weights=plan['pair_weights'],
            pair_schedule=[p for p,n in plan['pair_weights'].items() for _ in range(n)],common_bidder=plan['common_bidder'],
            audit_references=plan['audit_references'],two_self_rooms=False,
            target=len(keep),campaign=plan['campaign']+'-independent',title=plan['title']+' · independent collector',
            source_generation=old['identity'],source_completed=len(done),created_epoch=time.time(),
            source_sha256=source_hash(),runtime_sha256={n:sha(ROOT/n) for n in ('ops/gen5_runtime.py','ops/prepare_gen6_fast_selfplay.py')},
            plan_sha256=sha(plan_path),allocation_authority_commit='5b020bcd86ac32fc63559732832e57e796e00121',bidding_conditions=['self','common','native'])
        m['model_note']='Unchanged Gen6 fast actor:32 samples, lead belief only on opening lead, scorer after, full-list cutover trick7 capped256. Only 92.5% fast self-play and7.5% fast/BEN16. Gen3 retained only as tie-audit reference. Gap capture and50% tie audits unchanged; BEN forks disabled.'
        m['interpretation']='Self-play is training-only: one physical root table per family, null comparison IMPs and no fabricated strength estimate. Fast/BEN16 retains common and native auctions with swapped rooms. Completed predecessor records are immutable and retained separately. Only unused source families continue.'
        root.mkdir(parents=True)
        for folder in ('artifacts','assets'):shutil.copytree(source/folder,root/folder)
        for name in ('episodes','receipts','failures'):(root/name).mkdir()
        save([boards[i] for i in keep],root/'corpus.jsonl');atomic_json(root/'source-indices.json',keep)
        m.update(corpus_sha256=sha(root/'corpus.jsonl'),source_indices='source-indices.json',source_indices_sha256=sha(root/'source-indices.json'))
        m['identity']=digest(m);atomic_json(root/'manifest.json',m)
        atomic_json(root/'state.json',dict(manifest_identity=m['identity'],completed=0,target=len(keep),by_pair={},root_games=0,tables=0,epoch=time.time()))
        atomic_json(root/'heartbeat.json',dict(epoch=time.time(),completed=0,workers=4,ben_workers=1,in_flight=[]))
        verify_generation(root,m);return m
