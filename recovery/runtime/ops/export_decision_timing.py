"""Compute root-game decision latencies for a frozen score publication."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bridge_harness.decision_timing import from_record,merge
from bridge_harness.selfplay import atomic_json

def compute(path):
    with gzip.open(path,'rt') as f:record=json.load(f)
    return record['index'],record['manifest_identity'],from_record(record)

def export(run,feed):
    manifest=json.loads((run/'manifest.json').read_text());data=json.loads(feed.read_text())
    if data['manifest_identity']!=manifest['identity']:raise ValueError('Wrong timing/score cohort')
    cutoff=data['generated_epoch'];summary=merge();count=0
    index_file=feed.parent/'replays/data'/manifest['identity']/'index.json'
    index=json.loads(index_file.read_text());records=list(index.get('records',[]))
    for shard in index.get('record_shards',[]):records.extend(json.loads((index_file.parent/shard).read_text()))
    ids={int(r['id']) for r in records if r['completed_epoch']<=cutoff}
    if len(ids)!=data['completed']:raise ValueError('Published replay index differs from score snapshot')
    files=[run/'episodes'/f'{i:06d}.json.gz' for i in sorted(ids)]
    with ProcessPoolExecutor(max_workers=4) as pool:
        for i,identity,timing in pool.map(compute,files,chunksize=4):
            if identity!=manifest['identity'] or i not in ids:raise ValueError('Wrong game identity')
            summary=merge(summary,timing);count+=1
    if count!=data['completed']:raise ValueError('Timing game coverage differs from score snapshot')
    summary.update(cohort=manifest['identity'],completed_records=count,cutoff_epoch=cutoff,
        generated_epoch=time.time(),definition='Elapsed wall time per actual root-game card decision, including forced moves. Opening lead and later play are separate. Training forks, replayed prefixes, forced counterfactuals and fixed leads are excluded.')
    data['decision_timing']=summary
    data['collection'].update(running=False,status='retired-awaiting-v5',retired_bots=['4','4p'])
    atomic_json(feed,data)
    print(json.dumps(summary),flush=True)
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--feed',type=Path,required=True);a=p.parse_args()
    export(a.run.resolve(),a.feed.resolve())
