"""Preserve stopped substitution prefix and switch remaining batch to direct play."""
import argparse
from collections import Counter
from copy import deepcopy
import fcntl
from pathlib import Path
import shutil
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.improvement import read
from bridge_harness.corpus import load,save
from bridge_harness.selfplay import atomic_json
from bridge_harness.loop_registry import sha,source_hash
from bridge_harness.training import digest
from bridge_harness.direct_arena import schedule,summarize
from bridge_harness.bidding_env import deal_key

def switch(old,new):
    if not (old/'STOP').exists(): raise ValueError('Old run must be intentionally stopped')
    with (old/'.supervisor.lock').open('a+') as s, (old/'.writer.lock').open('a+') as w:
        for f in (s,w): fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if new.exists(): raise ValueError('Refusing to overwrite direct run')
        m=read(old/'manifest.json');rows=[read(p) for p in sorted((old/'receipts').glob('*.json'))]
        if len(rows)!=len(list((old/'episodes').glob('*.gz'))):raise ValueError('Incomplete receipts')
        completed={r['index'] for r in rows};families={r['family'] for r in rows}
        if len(completed)!=len(rows) or len(families)!=len(rows): raise ValueError('Duplicate prefix')
        boards=[b for i,b in enumerate(load(old/m['corpus'])) if i not in completed]
        if any(deal_key(b.hands,True) in families for b in boards):raise ValueError('Overlapping cohort')
        new.mkdir(parents=True)
        for folder in ('artifacts','bidding'):shutil.copytree(old/folder,new/folder)
        save(boards,new/'corpus.jsonl')
        updated=deepcopy(m);updated.pop('identity')
        updated.update(schema='direct-fork-generation-v1',protocol='direct-pairs-v1',target=len(boards),
            legacy_completed=len(rows),batch_target=m['target'],retained_training_runs=[str(old)],
            direct_versions=dict(A=m['candidate'],B=m['reference'],C='combined-v2'),
            source_sha256=source_hash(),corpus_sha256=sha(new/'corpus.jsonl'),
            pair_protocol='Two tables on same deal and auction; X NS/Y EW then Y NS/X EW; random order; IMP(NS1-NS2) favors X',
            allocation='4:2:1 per deterministically shuffled seven-board block',demotion_looks=[],
            admission='A provisional; descriptive separate pair results, no automatic cross-pair demotion',
            previous_protocol_manifest_sha256=sha(old/'manifest.json'),created_epoch=time.time())
        updated['pair_counts']=dict(Counter(schedule(updated,i)[0] for i in range(len(boards))))
        updated['identity']=digest(updated)
        atomic_json(new/'manifest.json',updated);atomic_json(new/'state.json',summarize([],updated))
        cfg=read(old/'training-config.json');cfg['transition']['sha256']=sha(ROOT/cfg['transition']['path'])
        atomic_json(new/'training-config.json',cfg)
        if (old/'next-round-multiscore.json').exists():shutil.copy2(old/'next-round-multiscore.json',new/'next-round-multiscore.json')
        handoff=dict(status='initialized-awaiting-verified-launch',run=str(new),checkout=str(ROOT),generation=m['generation'],
            protocol='direct-pairs-v1',legacy_run=str(old),legacy_completed=len(rows),target=len(boards),batch_target=m['target'],
            workers=2,manifest_identity=updated['identity'],pair_counts=updated['pair_counts'],
            restart_command=f'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -u ops/supervise_mixed.py supervise --run {new} --seconds 240 --workers 2',
            instruction='User corrected scope: direct matches NOW in this batch. Old STOP is permanent. Never pool substitution IMPs with direct matches. Preserve legacy training. Follow current.json; do not revive old collector.',epoch=time.time())
        atomic_json(new/'match-format-change.json',handoff)
        atomic_json(old/'match-format-change.json',handoff)
        atomic_json(old.parent/'match-format-change.json',handoff)
        atomic_json(old.parent/'current.json',handoff)
        print(handoff)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--old',type=Path,required=True);p.add_argument('--new',type=Path,required=True)
    a=p.parse_args();switch(a.old.resolve(),a.new.resolve())
