"""Freeze unused families for Max's fast-only collection mix."""
import json,shutil,time,fcntl,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.corpus import load,save
from bridge_harness.bidding_env import deal_key
from bridge_harness.loop_registry import sha,source_hash
from bridge_harness.training import digest
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
source=ROOT.parent/'gen6-ben64-capture/runs/gen6-chatgpt-ben64-capture-20261111'
root=ROOT/'runs/gen6-chatgpt-fast-selfplay-20261111'
assert not root.exists()
assert (source/'STOP').exists() and (source/'WATCHDOG_STOP').exists()
with (source/'.writer.lock').open('a+') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 old=json.loads((source/'manifest.json').read_text());assert digest({k:v for k,v in old.items() if k!='identity'})==old['identity']
 boards=load(source/old['corpus']);assert sha(source/old['corpus'])==old['corpus_sha256']
 receipts=[json.loads(p.read_text()) for p in sorted((source/'receipts').glob('*.json'))];done=set()
 assert not list((source/'failures').glob('*.json'))
 assert len(receipts)==len(list((source/'episodes').glob('*.json.gz')))
 for r in receipts:
  i=r['index'];assert i not in done and r['manifest_identity']==old['identity']
  assert r['family']==deal_key(boards[i].hands,True) and sha(source/'episodes'/f'{i:06d}.json.gz')==r['episode_sha256'];done.add(i)
 keep=[i for i in range(len(boards)) if i not in done]
 plan=json.loads((ROOT/'configs/round6-fast-selfplay.json').read_text())
 root.mkdir(parents=True)
 for folder in ['artifacts','assets','history']:shutil.copytree(source/folder,root/folder)
 history=root/'history'/old['identity'];history.mkdir()
 for name in ['manifest.json','corpus.jsonl','state.json','heartbeat.json','plan.json','source-indices.json','original-source-indices.json','ben-preflight.json','capture-equivalence.json']:
  if (source/name).exists():shutil.copy2(source/name,history/name)
 for folder in ['episodes','receipts','resolved-failures']:shutil.copytree(source/folder,history/folder)
 for folder in ['bridge_harness','ops','scripts','configs','native']:
  shutil.copytree(source.parents[1]/folder,history/'runtime'/folder,ignore=shutil.ignore_patterns('__pycache__'))
 for folder in ['episodes','receipts','failures']:(root/folder).mkdir()
 save([boards[i] for i in keep],root/'corpus.jsonl');atomic_json(root/'source-indices.json',keep)
 original=json.loads((source/'original-source-indices.json').read_text());atomic_json(root/'original-source-indices.json',[original[i] for i in keep])
 m={k:v for k,v in old.items() if k not in ['identity','prior_manifests','cutover']}
 m.update(campaign=plan['campaign'],title=plan['title'],target=len(keep),roster=plan['roster'],order=plan['roster'],pair_weights=plan['pair_weights'],pair_schedule=[p for p,n in plan['pair_weights'].items() for _ in range(n)],source_generation=old['identity'],source_completed=len(done),source_indices='source-indices.json',source_indices_sha256=sha(root/'source-indices.json'),created_epoch=time.time(),corpus_sha256=sha(root/'corpus.jsonl'),source_sha256=source_hash(),runtime_sha256={n:sha(ROOT/n) for n in ['ops/gen5_runtime.py','ops/export_gen5.py','ops/prepare_fast_selfplay.py','ops/smoke_gen6.py']},plan_sha256=sha(ROOT/'configs/round6-fast-selfplay.json'),two_self_rooms=False,model_note='Gen6 fast self-play (92.5%) and fast versus BEN16 (7.5%). Frozen fast networks and sample settings; Gen7 guess/gap capture and 50% tie audits retained. Self-play has no strength IMP estimate.',interpretation='Self-play provides training with one root table per deal; no IMP comparison. BEN16 uses common/native auctions and swapped rooms. Existing historical results remain separately preserved.')
 m['identity']=digest(m);atomic_json(root/'manifest.json',m);atomic_json(root/'plan.json',plan)
 atomic_json(root/'state.json',dict(manifest_identity=m['identity'],completed=0,target=len(keep),by_pair={},root_games=0,tables=0,failures=0,epoch=time.time()))
 atomic_json(root/'heartbeat.json',dict(epoch=time.time(),completed=0,workers=4,ben_workers=1,in_flight=[]))
 verify_generation(root,m)
 print(json.dumps(dict(identity=m['identity'],target=len(keep),retired=len(done))))
