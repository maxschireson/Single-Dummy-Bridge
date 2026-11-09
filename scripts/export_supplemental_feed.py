"""Export completed, replay-validated supplemental boards and dashboard views."""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scipy.stats import t
from bridge_harness.arena_pairs import pair_id,pair_members
from bridge_harness.runner import replay
from bridge_harness.selfplay import atomic_json

LABELS={str(i):'Gen '+str(i) for i in range(1,5)}
PAIRS=['44','43','42','41','32']

def stats(values):
    n=len(values);v=[x for x in values if x is not None]
    if not v:return dict(n=n,total=None,mean=None,variance=None,sd=None,se=None,ci=None,wins=0,ties=0,losses=0)
    mean=sum(v)/n;variance=sum((x-mean)**2 for x in v)/(n-1) if n>1 else None
    sd=math.sqrt(variance) if variance is not None else None;se=sd/math.sqrt(n) if sd is not None else None
    half=float(t.ppf(.975,n-1))*se if se is not None else None
    return dict(n=n,total=sum(v),mean=mean,variance=variance,sd=sd,se=se,
        ci=[mean-half,mean+half] if half is not None else None,
        wins=sum(x>0 for x in v),ties=sum(x==0 for x in v),losses=sum(x<0 for x in v))

def view(rows,own=False,window=0,pairs=None,labels=None):
    groups={};matrix={k:{} for k in (labels or LABELS)}
    for pair in (pairs or PAIRS):
        selected=[r for r in rows if r['pair']==pair]
        if window:selected=selected[-window:]
        if not selected:continue
        values=[r['own_imps' if own else 'imps'] for r in selected];s=stats(values);groups[pair]=s
        a,b=pair_members(pair);matrix[a][b]=s
        if a!=b:matrix[b][a]=stats([-v for v in values])
    return dict(groups=groups,matrix=matrix)

def export(root,out):
    m=json.loads((root/'manifest.json').read_text());status=json.loads((root/'status.json').read_text())
    cohort=m['identity'];now=time.time();records=[];shards=defaultdict(dict);seen=set()
    labels={k:v['label'] for k,v in m['bots'].items()}
    pairs=list(dict.fromkeys(pair_id(*pair_members(p)) for p in m.get('pair_schedule',PAIRS)))
    order=m.get('display_order',['4','3','2','1'])
    cached={}
    for old in (out/'arena/replays/data'/cohort).glob('boards-*.json'):
        cached.update(json.loads(old.read_text()))
    for path in sorted((root/'episodes').glob('*.json.gz')):
        raw=path.read_bytes();checksum=hashlib.sha256(raw).hexdigest();key=str(int(path.name.split('.')[0]))
        if key in cached:
            full=cached[key]
            if full['episode_sha256']!=checksum:raise ValueError('Previously published episode changed')
            if full['family'] in seen:raise ValueError('Duplicate deal family')
            seen.add(full['family']);row={k:v for k,v in full.items() if k not in ('conditions','board','tables')}
            records.append(row);shards[row['shard']][key]=full;continue
        r=json.loads(gzip.decompress(raw))
        if r['manifest_identity']!=cohort:raise ValueError('Manifest mismatch')
        if r['family'] in seen:raise ValueError('Duplicate deal family')
        seen.add(r['family'])
        for table in r['unique_tables'].values():
            if table.get('schema_version')!='v4-passed-out-v1':replay(table)
        pair=r['pair'];a,b=pair_members(pair);index=r['index'];conditions={}
        for regime in ('common','own'):
            source=r['regimes'].get('native' if regime=='own' else 'common',r['regimes'].get('self'))
            tables=[]
            for table_id in source['tables']:
                e=r['unique_tables'][table_id];b=e['board'];t0=e['tables'][0]
                tables.append(dict(contract=b.get('contract'),declarer=b.get('declarer'),auction=b.get('auction',[]),
                    assignments=[a if v=='candidate' else b for v in e['assignments']],
                    ns_score=t0['ns_score'],declarer_tricks=t0.get('declarer_tricks'),
                    plays=[a['seat']+a['card'] for a in t0['actions']]))
            conditions[regime]=dict(tables=tables,imps=source['imps'],label='Common v4 bidder' if regime=='common' else 'Historical bidders')
        common=conditions['common']['tables'];own=conditions['own']['tables']
        different=any(a['auction']!=b['auction'] for a,b in zip(common,own))
        first=r['unique_tables'][next(iter(r['unique_tables']))]['board']
        row=dict(id=str(index),index=index,pair=pair,imps=conditions['common']['imps'],own_imps=conditions['own']['imps'],
            completed_epoch=r['completed_epoch'],family=r['family'],episode_sha256=hashlib.sha256(raw).hexdigest(),
            different_bidding=different,dd_bidding_imps={},shard=f'boards-{index//100:05d}.json',board_id=first['id'],
            scores=[t0['ns_score'] for t0 in common],contracts=[{k:t0[k] for k in ('contract','declarer')} for t0 in common],
            own_scores=[t0['ns_score'] for t0 in own],own_contracts=[{k:t0[k] for k in ('contract','declarer')} for t0 in own])
        records.append(row);shards[row['shard']][str(index)]={**row,'conditions':conditions,'board':first,'tables':common}
    replay_dir=out/'arena/replays/data'/cohort;replay_dir.mkdir(parents=True,exist_ok=True)
    for name,rows in shards.items():atomic_json(replay_dir/name,rows)
    title=m.get('title','ChatGPT Gen 4 supplement');versions={k:s['identity'] for k,s in m['bots'].items()}
    record_shards=[]
    for offset in range(0,len(records),100):
        name=f'index-{offset//100:05d}.json';atomic_json(replay_dir/name,records[offset:offset+100]);record_shards.append(name)
    atomic_json(replay_dir/'index.json',dict(schema='bridge-replay-index-v1',cohort=cohort,title=title,labels=labels,pairs=pairs,versions=versions,records=[],record_shards=record_shards))
    atomic_json(out/'arena/replays/catalog.json',dict(schema='bridge-replay-catalog-v1',cohorts=[dict(id=cohort,title=title,count=len(records),index_url=f'data/{cohort}/index.json')]))
    contiguous=0;indices={r['index'] for r in records}
    while contiguous in indices:contiguous+=1
    rates={}
    for minutes in (5,15,30,60):
        n=sum(r['completed_epoch']>=now-minutes*60 for r in records)
        span=min(minutes*60,max(1,now-json.loads((root/'created_epoch.json').read_text())))
        rates[str(minutes)]=dict(pairs=n,per_hour=n*3600/span,full_window=span>=minutes*60)
    curves={p:[] for p in pairs if pair_members(p)[0]!=pair_members(p)[1]}
    for pair in curves:
        rows=[r for r in records if r['pair']==pair]
        for n in sorted(set(list(range(10,len(rows)+1,10))+([len(rows)] if rows else []))):
            curves[pair].append(dict(index=n,**stats([r['imps'] for r in rows[:n]])))
    d=dict(generated_epoch=now,campaign=title,manifest_identity=cohort,labels=labels,order=order,versions=versions,
        completed=len(records),target=m['target'],contiguous=contiguous,failures=status['failures'],configured_workers=status['workers'],worker_experiment=None,
        last_commit_epoch=max((r['completed_epoch'] for r in records),default=None),rates=rates,
        views={str(n):view(records,window=n,pairs=pairs,labels=labels) for n in (0,100,500,1000)},
        own_views={str(n):view(records,own=True,window=n,pairs=pairs,labels=labels) for n in (0,100,500,1000)},curves=curves,
        model_artifacts={k:s['artifact_sha256'] for k,s in m['bots'].items()},
        interpretation='Independent cohort, 32 samples, two root tables per board, random policy audits. Common-v4 and historical-bidder results remain separate. Self-play supplies training only. Student-t intervals are exploratory and unadjusted for repeated looks. Only complete replay-validated boards are included. Cohorts are selectable separately; their IMP statistics are not pooled.',
        feed=dict(published_epoch=now,interval_seconds=60,next_update_epoch=now+60),
        collection=dict(updated_epoch=status['updated_epoch'],running=now-status['updated_epoch']<30,workers=status['workers']))
    atomic_json(out/'arena/data.json',d)
    atomic_json(out/'arena/manifest.json',m)
    print(json.dumps(dict(completed=len(records),tables=sum(len(v['tables']) for s in shards.values() for v in s.values()),
        rate=rates['5'],files=len(list(out.rglob('*.json'))),output=str(out))))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args();export(a.run,a.out)
