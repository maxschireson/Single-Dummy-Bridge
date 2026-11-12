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
from bridge_harness.runner import replay
from bridge_harness.selfplay import atomic_json

from bridge_harness.arena_pairs import pair_members
from bridge_harness.decision_timing import merge
LABELS={}
PAIRS=[]

def gen6_differences(row):
    """Paired auction-condition decomposition, in candidate-oriented IMPs."""
    play=row['imps'];total=row['own_imps']
    if play is None and total is None:return dict(play=None,bidding=None,total=None)
    return dict(play=play,bidding=total-play,total=total)

def difference_views(rows):
    result={}
    for window in (0,100,500,1000):
        groups={}
        for pair in PAIRS:
            selected=[r for r in rows if r['pair']==pair]
            if window:selected=selected[-window:]
            if selected:
                groups[pair]={name:stats([gen6_differences(r)[name] for r in selected])
                              for name in ('bidding','play','total')}
                groups[pair]['different_bidding']=sum(r['different_bidding'] for r in selected)
        result[str(window)]=dict(groups=groups)
    return result

def stats(values):
    n=len(values);v=[x for x in values if x is not None]
    if not v:return dict(n=n,total=None,mean=None,variance=None,sd=None,se=None,ci=None,wins=0,ties=0,losses=0)
    mean=sum(v)/n;variance=sum((x-mean)**2 for x in v)/(n-1) if n>1 else None
    sd=math.sqrt(variance) if variance is not None else None;se=sd/math.sqrt(n) if sd is not None else None
    half=float(t.ppf(.975,n-1))*se if se is not None else None
    return dict(n=n,total=sum(v),mean=mean,variance=variance,sd=sd,se=se,
        ci=[mean-half,mean+half] if half is not None else None,
        wins=sum(x>0 for x in v),ties=sum(x==0 for x in v),losses=sum(x<0 for x in v))

def view(rows,own=False,window=0):
    groups={};matrix={k:{} for k in LABELS}
    for pair in PAIRS:
        selected=[r for r in rows if r['pair']==pair]
        if window:selected=selected[-window:]
        if not selected:continue
        values=[r['own_imps' if own else 'imps'] for r in selected];s=stats(values);groups[pair]=s
        a,b=pair_members(pair);matrix[a][b]=s
        if a!=b:matrix[b][a]=stats([-v for v in values])
    return dict(groups=groups,matrix=matrix)

def export(root,out):
    global LABELS, PAIRS
    m=json.loads((root/'manifest.json').read_text());LABELS=m['labels'];status=json.loads((root/'heartbeat.json').read_text())
    policy_path=root/'statistics-policy.json'
    policy=json.loads(policy_path.read_text()) if policy_path.exists() else {}
    eligible=set(policy.get('eligible_pairs',m['pair_weights']))
    PAIRS=[p for p in m['pair_weights'] if p in eligible]
    cohort=m['identity'];now=time.time();records=[];shards=defaultdict(dict);seen=set()
    cached={}
    for old in (out/'arena/replays/data'/cohort).glob('boards-*.json'):
        cached.update(json.loads(old.read_text()))
    episodes=sorted((root/'episodes').glob('*.json.gz'))
    for path in episodes:
        raw=path.read_bytes();checksum=hashlib.sha256(raw).hexdigest();key=str(int(path.name.split('.')[0]))
        if key in cached:
            full=cached[key]
            if full['episode_sha256']!=checksum:raise ValueError('Previously published episode changed')
            if full['pair'] not in eligible:continue
            if full['family'] in seen:raise ValueError('Duplicate deal family')
            seen.add(full['family']);row={k:v for k,v in full.items() if k not in ('conditions','board','tables')}
            records.append(row);shards[row['shard']][key]=full;continue
        r=json.loads(gzip.decompress(raw))
        if r['manifest_identity']!=cohort:raise ValueError('Manifest mismatch')
        if r['pair'] not in eligible:continue
        if r['family'] in seen:raise ValueError('Duplicate deal family')
        seen.add(r['family'])
        for table in r['unique_tables'].values():
            if table.get('schema_version')!='v4-passed-out-v1':replay(table)
        pair=r['pair'];index=r['index'];conditions={}
        for regime in ('common','own'):
            source=r['regimes'].get('native' if regime=='own' else 'common',r['regimes'].get('self'))
            tables=[]
            for table_id in source['tables']:
                e=r['unique_tables'][table_id];b=e['board'];t0=e['tables'][0]
                tables.append(dict(contract=b.get('contract'),declarer=b.get('declarer'),auction=b.get('auction',[]),
                    assignments=[pair_members(pair)[0] if v=='candidate' else pair_members(pair)[1] for v in e['assignments']],
                    ns_score=t0['ns_score'],declarer_tricks=t0.get('declarer_tricks'),
                    plays=[a['seat']+a['card'] for a in t0['actions']]))
            conditions[regime]=dict(tables=tables,imps=source['imps'],label='Self-play (training only)' if pair_members(pair)[0]==pair_members(pair)[1] else ('Common Gen6 bidder' if m.get('variant') in ('6','7') else 'Common v5 bidder') if regime=='common' else 'Native partnership bidders')
        common=conditions['common']['tables'];own=conditions['own']['tables']
        different=any(a['auction']!=b['auction'] for a,b in zip(common,own))
        first=r['unique_tables'][next(iter(r['unique_tables']))]['board']
        row=dict(decision_timing=r['decision_timing'],id=str(index),index=index,pair=pair,imps=conditions['common']['imps'],own_imps=conditions['own']['imps'],
            completed_epoch=r['completed_epoch'],family=r['family'],episode_sha256=hashlib.sha256(raw).hexdigest(),
            different_bidding=different,dd_bidding_imps={},shard=f'boards-{index//100:05d}.json',board_id=first['id'],
            scores=[t0['ns_score'] for t0 in common],contracts=[{k:t0[k] for k in ('contract','declarer')} for t0 in common],
            own_scores=[t0['ns_score'] for t0 in own],own_contracts=[{k:t0[k] for k in ('contract','declarer')} for t0 in own])
        records.append(row);shards[row['shard']][str(index)]={**row,'conditions':conditions,'board':first,'tables':common}
    if m.get('variant') in ('6','7'):
        for row in records:
            row['differences']=gen6_differences(row)
            shards[row['shard']][str(row['index'])]['differences']=row['differences']
    replay_dir=out/'arena/replays/data'/cohort;replay_dir.mkdir(parents=True,exist_ok=True)
    for name,rows in shards.items():atomic_json(replay_dir/name,rows)
    title=policy.get('title',m.get('title','Gen 5R · Codex' if m.get('variant')=='5R' else 'Gen 5 · Codex'));versions={k:s['identity'] for k,s in m['bots'].items()}
    record_shards=[];record_shard_sha256={}
    for offset in range(0,len(records),100):
        rows=records[offset:offset+100];base=f'index-{offset//100:05d}'
        atomic_json(replay_dir/(base+'.json'),rows)
        checksum=hashlib.sha256((replay_dir/(base+'.json')).read_bytes()).hexdigest()
        name=base+'-'+checksum+'.json'
        if not (replay_dir/name).exists():atomic_json(replay_dir/name,rows)
        record_shards.append(name);record_shard_sha256[name]=checksum
    atomic_json(replay_dir/'index.json',dict(schema='bridge-replay-index-v1',cohort=cohort,title=title,labels=LABELS,pairs=PAIRS,versions=versions,supports_own_bidding=True,records=[],record_shards=record_shards,record_shard_sha256=record_shard_sha256))
    atomic_json(out/'arena/replays/catalog.json',dict(schema='bridge-replay-catalog-v1',cohorts=[dict(id=cohort,title=title,count=len(records),index_url=f'data/{cohort}/index.json')]))
    contiguous=0;indices={r['index'] for r in records}
    while contiguous in indices:contiguous+=1
    now=time.time()  # Every included completion precedes the linked snapshot cutoff.
    rates={}
    for minutes in (5,15,30,60):
        n=sum(r['completed_epoch']>=now-minutes*60 for r in records)
        span=min(minutes*60,max(1,now-m['created_epoch']))
        rates[str(minutes)]=dict(pairs=n,per_hour=n*3600/span,full_window=span>=minutes*60)
    curves={p:[] for p in PAIRS if pair_members(p)[0]!=pair_members(p)[1]}
    for pair in curves:
        rows=[r for r in records if r['pair']==pair]
        for n in sorted(set(list(range(10,len(rows)+1,10))+([len(rows)] if rows else []))):
            curves[pair].append(dict(index=n,**stats([r['imps'] for r in rows[:n]])))
    d=dict(generated_epoch=now,campaign=title,manifest_identity=cohort,labels=LABELS,order=m['order'],versions=versions,
        completed=len(records),target=policy.get('target',m['target']),contiguous=contiguous,failures=len(list((root/'failures').glob('*.json'))),configured_workers=0 if policy.get('retired') else status['workers'],worker_experiment=None,
        last_commit_epoch=max((r['completed_epoch'] for r in records),default=None),rates=rates,
        views={str(n):view(records,window=n) for n in (0,100,500,1000)},
        own_views={str(n):view(records,own=True,window=n) for n in (0,100,500,1000)},curves=curves,decision_timing=merge(*(r.get('decision_timing') for r in records)),
        model_artifacts={k:s['artifact_sha256'] for k,s in m['bots'].items()},
        interpretation='Gen5 and historical opponents both use 32 samples in historical comparisons. Gen5 uses 192 only against BEN at 16 samples and its identical-network 32-sample control. Earlier 192-vs-historical games are excluded from statistics and preserved for training. Each hand has common-v5 and native-partnership bidding conditions; identical auctions reuse played games. Pair allocations are 40% 4b, 20% Gen3, 15% Gen2, 5% Gen1, 5% BEN and 15% 32-vs-192 Gen5. Independent fresh families; report auction conditions separately. Exploratory Student-t intervals are not adjusted for repeated monitoring.',
        feed=dict(published_epoch=now,interval_seconds=60,next_update_epoch=now+60),
        model_note='Gen5: promoted dense belief, attention policy and bidder. Gen5/4b/3/2/1 comparisons use 32 vs 32. Gen5 uses 192 vs BEN (16) and Gen5 (32) only; the two Gen5 actors share all network weights.', source_cohort_overlap=False, allocation=m['pair_weights'], statistics_policy=policy,
        collection=dict(updated_epoch=status['epoch'],running=not policy.get('retired') and now-status['epoch']<30,workers=0 if policy.get('retired') else status['workers'],total_completed=len(episodes),training_only_completed=len(episodes)-len(records)))
    if m.get('variant') in ('5R','5RZ','6','7'):
        d['interpretation']=m['interpretation']
        d['model_note']='Gen5R uses the same bidder, belief and policy as Gen5; only large-position layout selection and weighting change. Nominal 32/192 are DDS ceilings, drawing pools of 128/768. Original Gen5 (32) is retained as the random-sampling control.'
        if m.get('model_note'):d['model_note']=m['model_note']
    if m.get('variant') in ('6','7'):
        d['difference_views']=difference_views(records)
        d['difference_definition']=dict(unit='IMPs per board, candidate minus opponent',
            play='Common Gen6-bidder auction result',total='Native partnership-bidder auction result',
            bidding='Native minus common on the same board; includes auction/play interaction',
            uncertainty='Student-t intervals on paired per-board differences; exploratory, unadjusted for repeated monitoring')
    atomic_json(out/'arena/data.json',d)
    atomic_json(out/'arena/manifest.json',m)
    print(json.dumps(dict(completed=len(records),tables=sum(len(v['tables']) for s in shards.values() for v in s.values()),
        rate=rates['5'],files=len(list(out.rglob('*.json'))),output=str(out))))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args();export(a.run,a.out)
