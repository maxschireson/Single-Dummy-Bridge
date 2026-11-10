"""Measure extra exact-auction replay work using a frozen probe."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.bidding_refresh import digest,terminal_scores
from bridge_harness.bidding_play_cache import MissingPlayCache
from bridge_harness.bidding_loop import atomic_json
from bridge_harness.core import Board,auction_contract


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',required=True);p.add_argument('--probes',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--play-root',type=Path,required=True)
    p.add_argument('--dds-library',required=True);p.add_argument('--limit',type=int,default=30);a=p.parse_args()
    by={r['family']:r for r in json.load(open(a.data)) if r['source']=='play'}
    summary={};requests={}
    for label in ['greedy_dev','sampled_train']:
        rows=json.load(open(a.probes/(label+'-probe.json')));counts=Counter();unique={}
        for r in rows:
            d=by[r['family']];b=Board.from_dict(d['board'])
            for room in r['tables']:
                counts['rooms']+=1;c=auction_contract(b.dealer,room['calls'])
                if c is None or digest(room['calls']) in d['auction_outcomes']:category='exact_known_or_passed_out'
                elif f'{c.trump}/{c.declarer}' not in d['outcomes']:category='new_strain_declarer'
                elif any(x['contract']==c.text() and x['declarer']==c.declarer for x in d['auction_outcomes'].values()):category='new_auction_same_contract'
                else:category='new_contract_known_strain'
                counts[category]+=1
                key=digest([r['family'],room['calls']]);unique[key]=category
                if category=='new_contract_known_strain':requests.setdefault(key,(b,room['calls'],d))
        summary[label]=dict(rooms=dict(counts),unique=dict(Counter(unique.values())),deals=len(rows))
    atomic_json(a.out/'exact-coverage-probe.json',summary);print(json.dumps(summary),flush=True)
    spec=json.load(open(a.play_root/'manifest.json'))['bots']['3']
    cache=MissingPlayCache(a.out/'play-cache',a.play_root,spec,dds_library=a.dds_library)
    selected=sorted(requests.items())[:a.limit];results=[]
    for i,(_, (b,calls,d)) in enumerate(selected):
        cache.score(b,calls)
        path=cache.root/(cache.key(b,calls)+'.json.gz');r=json.load(gzip.open(path,'rt'))
        c=auction_contract(b.dealer,calls);old=d['outcomes'][f'{c.trump}/{c.declarer}'];new=r['tables'][0]['declarer_tricks']
        results.append(dict(family=d['family'],contract=c.text(),declarer=c.declarer,seconds=r['seconds'],
                            old_tricks=old,new_tricks=new,outside_old_range=not min(old)<=new<=max(old)))
        atomic_json(a.out/'same-strain-replay-benchmark-rows.json',results)
        if (i+1)%5==0:print(json.dumps(dict(played=i+1,total=len(selected),seconds=sum(x['seconds'] for x in results))),flush=True)
    values=[r['seconds'] for r in results]
    stats=dict(played=len(values),total_seconds=sum(values),mean_seconds=float(np.mean(values)),
               median_seconds=float(np.median(values)),p90_seconds=float(np.quantile(values,.9)),
               max_seconds=max(values),outside_old_trick_range=sum(r['outside_old_range'] for r in results),
               note='Different play seeds and sometimes different clean bot versions; not a controlled causal comparison')
    atomic_json(a.out/'same-strain-replay-benchmark.json',stats);print(json.dumps(stats),flush=True);cache.close()


if __name__=='__main__':main()
