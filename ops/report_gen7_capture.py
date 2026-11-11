"""Read-only capture audit; publish the first report after 2,000 non-BEN root tables.

Episode hashes are checked against receipts. Errors and progress are saved for recovery.
This process never changes an episode, receipt or collector configuration.
"""
import argparse
from collections import defaultdict
import fcntl
import gzip
import json
import math
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.core import Board,Game,card
from bridge_harness.loop_registry import sha
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest


def clustered(values, families):
    n=len(values)
    if not n:return dict(n=0,mean=None,se=None,deals=0)
    mean=sum(values)/n;scores=defaultdict(float)
    for value,family in zip(values,families):scores[family]+=value-mean
    m=len(scores)
    se=math.sqrt(m/(m-1)*sum(s*s for s in scores.values()))/n if m>1 else None
    return dict(n=n,mean=mean,se=se,deals=m)


def summarize(rows):
    families=[r['family'] for r in rows]
    result={key:clustered([r[key] for r in rows],families) for key in ('realized','estimated')}
    result['difference']=clustered([r['realized']-r['estimated'] for r in rows],families)
    result['result_differs_fraction']=sum(abs(r['realized'])>1e-9 for r in rows)/len(rows) if rows else None
    return result


def correlation(rows):
    groups=defaultdict(list)
    for r in rows:groups[r['table']].append(r['realized']-r['estimated'])
    n=sum(map(len,groups.values()));k=len(groups)
    if k<2 or n<=k:return dict(icc=None,tables=k,forks=n)
    mean=sum(map(sum,groups.values()))/n
    between=sum(len(v)*(sum(v)/len(v)-mean)**2 for v in groups.values())/(k-1)
    within=sum(sum((x-sum(v)/len(v))**2 for x in v) for v in groups.values())/(n-k)
    size=(n-sum(len(v)**2 for v in groups.values())/n)/(k-1)
    denominator=between+(size-1)*within
    return dict(icc=(between-within)/denominator if denominator else None,tables=k,forks=n,
                method='one-way random-effects ANOVA ICC, unequal table sizes')


def phase(ply):
    if ply==0:return 'lead'
    trick=ply//4+1
    return 'tricks1-4' if trick<=4 else 'tricks5-8' if trick<=8 else 'tricks9-13'


def touching(record,event):
    game=Game(Board.from_dict(record['board']))
    for a in record['tables'][event['candidate_table']]['actions'][:event['ply']]:game.play(card(a['card']))
    a,b=card(event['candidate_card']),card(event['reference_card'])
    # Same-suit rank sequence: any ranks between the two cards must be held by
    # this hand or already played. An outstanding intervening opponent rank breaks it.
    hand=game.hands[event['actor']];known=hand|{c for _,c in game.history}
    return a//13==b//13 and a in hand and b in hand and all(c in known for c in range(min(a,b)+1,max(a,b)))


def deal_rate(run):
    epochs=[json.loads(p.read_text())['completed_epoch'] for p in (run/'receipts').glob('*.json')]
    duration=max(epochs)-min(epochs) if len(epochs)>1 else 0
    return dict(deals=len(epochs),elapsed_seconds=duration,deals_per_hour=(len(epochs)-1)*3600/duration if duration else None,
                method='completion span, all matchups; includes initialization and BEN lane')


def report(run,before,threshold=2000,force=False):
    manifest=json.loads((run/'manifest.json').read_text())
    if digest({k:v for k,v in manifest.items() if k!='identity'})!=manifest['identity']:raise ValueError('Manifest changed')
    if not manifest.get('gap_fork',{}).get('per_band'):raise ValueError('Capture is not enabled')
    receipts=sorted((run/'receipts').glob('*.json'))
    # Before the reporting threshold, read small receipts only; reserve gzip verification
    # and analysis for a possible full report, rather than competing with the collector.
    possible=0
    for p in receipts:
        r=json.loads(p.read_text())
        if r['manifest_identity']!=manifest['identity']:raise ValueError('Receipt manifest mismatch')
        if not any(manifest['bots'][k].get('engine')=='ben' for k in r['pair'].split('~')):possible+=r['root_games']
    if possible<threshold and not force:
        progress=dict(status='collecting',epoch=time.time(),manifest=manifest['identity'],root_tables=None,
                      eligible_root_tables_upper_bound=possible,threshold=threshold,episodes_scanned=0)
        atomic_json(run/'gen7-capture-monitor.json',progress);return progress
    roots=[];episodes=0;gaps=[];ties=[];skips=defaultdict(int);root_cpu=gap_cpu=0.
    for receipt in receipts:
        r=json.loads(receipt.read_text());path=run/'episodes'/f"{r['index']:06d}.json.gz"
        if r['manifest_identity']!=manifest['identity'] or sha(path)!=r['episode_sha256']:raise ValueError('Episode receipt mismatch')
        with gzip.open(path,'rt') as f:episode=json.load(f)
        episodes+=1
        for key,record in episode['unique_tables'].items():
            if 'gap_forks' not in record or len(roots)>=threshold:continue
            root=record['tables'][0]
            if not root['actions']:continue
            table=f"{r['index']}/{key}";roots.append(table);root_cpu+=root['cpu_seconds'];gap_cpu+=record['compute']['gap_cpu']
            for event in record.get('budget_skips',[]):
                if event['reason']=='gap-fork-budget':skips[str(event['band'])]+=1
            for event in record['gap_forks']:
                gaps.append(dict(family=episode['family'],table=table,band=event['band'],phase=phase(event['ply']),
                    realized=event['realized_cost_tricks'],estimated=event['estimated_gap']))
            declarer=Board.from_dict(record['board']).contract.declarer
            for event in record['audits']:
                if event['identical_action']:continue
                parent=record['tables'][event['candidate_table']];fork=record['tables'][event['reference_table']]
                sign=1 if event['actor']%2==declarer%2 else -1
                ties.append(dict(family=episode['family'],table=table,touching=touching(record,event),phase=phase(event['ply']),
                    realized=sign*(parent['declarer_tricks']-fork['declarer_tricks']),estimated=0.))
        if len(roots)>=threshold:break
    progress=dict(status='ready' if len(roots)>=threshold else 'collecting',epoch=time.time(),manifest=manifest['identity'],
                  root_tables=len(roots),threshold=threshold,episodes_scanned=episodes)
    atomic_json(run/'gen7-capture-monitor.json',progress)
    if len(roots)<threshold and not force:return progress
    by_band={};noise={}
    for band in range(len(manifest['gap_fork']['bands'])+1):
        selected=[r for r in gaps if r['band']==band]
        by_band[str(band)]=dict(forks=len(selected),forks_per_root=len(selected)/len(roots) if roots else None,budget_skips=skips[str(band)],
                              overall=summarize(selected),phases={p:summarize([r for r in selected if r['phase']==p]) for p in ('lead','tricks1-4','tricks5-8','tricks9-13')})
    for kind in (True,False):
        selected=[r for r in ties if r['touching']==kind]
        noise['touching' if kind else 'non_touching']=dict(overall=summarize(selected),
            phases={p:summarize([r for r in selected if r['phase']==p]) for p in ('lead','tricks1-4','tricks5-8','tricks9-13')})
    result=dict(progress,status='completed' if len(roots)>=threshold else 'interim',gap_fork=manifest['gap_fork'],
        gap_forks=len(gaps),gap_forks_per_root=len(gaps)/len(roots) if roots else None,root_cpu=root_cpu,gap_cpu=gap_cpu,
        added_cpu_share=gap_cpu/root_cpu if root_cpu else None,bands=by_band,
        residual_within_table_correlation=correlation(gaps),tie_audit_noise_control=noise,
        rate_before=deal_rate(before),rate_after=deal_rate(run),
        uncertainty='Means and standard errors cluster by deal family. Rates compare observed cohort lifetimes with the same match mix.',
        touching_definition='Same-suit sequence in the actor hand, allowing publicly played intervening ranks; no outstanding intervening opponent rank.')
    atomic_json(run/'gen7-capture-report.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--before',type=Path,required=True)
    p.add_argument('--threshold',type=int,default=2000);p.add_argument('--watch',action='store_true');p.add_argument('--force',action='store_true');a=p.parse_args()
    with (a.run/'.capture-report.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        atomic_json(a.run/'capture-report-process.json',dict(pid=os.getpid(),epoch=time.time(),source=str(ROOT)))
        while True:
            try:
                result=report(a.run,a.before,a.threshold,a.force)
                print(json.dumps({k:result[k] for k in ('status','root_tables','epoch')}),flush=True)
                if result['status']!='collecting' or not a.watch:break
            except Exception as e:
                atomic_json(a.run/'gen7-capture-monitor.json',dict(status='retrying',epoch=time.time(),error=repr(e)))
                if not a.watch:raise
            time.sleep(60)
