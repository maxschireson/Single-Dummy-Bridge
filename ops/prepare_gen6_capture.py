"""Freeze a logging/fork-only Gen6 successor, preserving actors, mix and completed families."""
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
from ops.prepare_ben_round5 import validate
import configparser


def prepare(root,source,plan_path,enabled=True):
    root,source=Path(root).resolve(),Path(source).resolve()
    if root.exists():raise ValueError('Refusing to overwrite frozen run')
    if not all((source/n).exists() for n in ('STOP','WATCHDOG_STOP')):raise ValueError('Drain source and disable watchdog first')
    plan=json.loads(Path(plan_path).read_text());gap=gap_fork_block(plan)
    if gap is None or gap['per_band']!=2:raise ValueError('Expected adopted Gen7 gap-fork block')
    with (source/'.writer.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        old=json.loads((source/'manifest.json').read_text());verify_source(source,old)
        if old.get('variant')!='6':raise ValueError('Expected Gen6 source')
        if old['pair_weights']!=plan['pair_weights'] or {k:v['identity'] for k,v in old['bots'].items()}!=plan['preserve_actor_identities']:
            raise ValueError('Capture plan must preserve the active allocation and actor identities')
        if old['audit']!=plan['audit'] or old['ben_audit']!=plan['ben_audit']:raise ValueError('Capture must preserve audit budgets')
        if list((source/'failures').glob('*.json')):raise ValueError('Inspect preserved failures first')
        boards=list(load(source/old['corpus']));done=set()
        if len(list((source/'episodes').glob('*.json.gz')))!=len(list((source/'receipts').glob('*.json'))):raise ValueError('Incomplete source records')
        for p in (source/'receipts').glob('*.json'):
            r=json.loads(p.read_text());i=r['index']
            if i in done or not 0<=i<len(boards) or r['manifest_identity']!=old['identity']:raise ValueError('Changed source receipt identity')
            if r['family']!=deal_key(boards[i].hands,True) or r['episode_sha256']!=sha(source/'episodes'/f'{i:06d}.json.gz'):raise ValueError('Source receipt/episode mismatch')
            done.add(i)
        keep=[i for i in range(old['target']) if i not in done]
        if not keep:raise ValueError('No unplayed boards')
        m=deepcopy(old);m.pop('identity')
        upgrade=plan.get('upgrade_ben')
        if upgrade:
            if (upgrade['from'],upgrade['to'],upgrade['samples'])!=('ben32','ben64',64):raise ValueError('Expected authorized BEN32 to BEN64 upgrade')
            c=configparser.ConfigParser(interpolation=None);c.read(upgrade['profile']);validate(c,64)
            spec=m['bots'].pop('ben32');spec.pop('identity')
            spec.update(id='ben-64',samples=64,url=upgrade['url'],config='assets/ben-64.conf')
            spec['artifact_sha256']['config']=sha(upgrade['profile']);spec['identity']=digest(spec);m['bots']['ben64']=spec
            m['roster']=['ben64' if k=='ben32' else k for k in m['roster']]
            m['order']=['ben64' if k=='ben32' else k for k in m['order']]
            m['labels'].pop('ben32',None);m['labels']['ben64']='BEN (64)'
            m['pair_weights']={p.replace('~ben32','~ben64'):n for p,n in m['pair_weights'].items()}
            m['pair_schedule']=[p for p,n in m['pair_weights'].items() for _ in range(n)]
        m.pop('gap_fork',None)
        if enabled:m['gap_fork']=gap
        m.update(target=len(keep),campaign='gen6-gen7-capture-20261111'+('' if enabled else '-equivalence-control'),title='Gen 6 · Gen7 data capture',
            created_epoch=time.time(),source_generation=old['identity'],source_completed=len(done),source_indices='source-indices.json',
            source_sha256=source_hash(),runtime_sha256={n:sha(ROOT/n) for n in ('ops/gen5_runtime.py','ops/prepare_gen6_capture.py')},
            plan_sha256=sha(plan_path),capture_source_commit='5e82f769a0e989ee10a6cb911a793a964d1b6ff5')
        m['model_note']='Frozen Gen6 networks: opening-lead belief net, then scorer; fast32/list trick7, medium256/list trick6, list solve cap256. BEN16 vs fast and BEN64 vs medium each receive 7.5%; other matchups unchanged. Gen7 training capture adds guess-size/best-share logs and post-commit gap-banded forks; tie audits stay at 50%; no gap forks on either BEN matchup.' if upgrade else old['model_note']+' Same frozen actors and play. Gen7 training capture adds guess-size/best-share logs and post-commit gap-banded forks; tie audits stay at 50%; no gap forks on either BEN matchup.'
        root.mkdir(parents=True)
        for folder in ('artifacts','assets'):shutil.copytree(source/folder,root/folder)
        if upgrade:shutil.copy2(upgrade['profile'],root/'assets/ben-64.conf')
        for name in ('episodes','receipts','failures'):(root/name).mkdir()
        save([boards[i] for i in keep],root/'corpus.jsonl');atomic_json(root/'source-indices.json',keep)
        m.update(corpus_sha256=sha(root/'corpus.jsonl'),source_indices_sha256=sha(root/'source-indices.json'))
        m['identity']=digest(m);atomic_json(root/'manifest.json',m)
        atomic_json(root/'state.json',dict(manifest_identity=m['identity'],completed=0,target=len(keep),by_pair={},root_games=0,tables=0,epoch=time.time()))
        atomic_json(root/'heartbeat.json',dict(epoch=time.time(),completed=0,workers=4,ben_workers=1,in_flight=[]))
        verify_generation(root,m);return m
