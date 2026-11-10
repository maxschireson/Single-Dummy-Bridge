"""Augment a frozen clean dataset with exact historical auction support."""
import argparse
from collections import defaultdict,Counter
import gzip
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.bidding_refresh import board_key,digest,sha
from bridge_harness.bidding_loop import atomic_json
from bridge_harness.core import Board


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();data=json.load(open(a.source/'dataset.json'));sources=json.load(open(a.source/'sources.json'))
    byboard={board_key(Board.from_dict(r['board'])):r for r in data if r['source']=='play'}
    for r in byboard.values():r['auction_outcomes']={}
    byfile=defaultdict(list)
    for s in sources:byfile[s['path']].append(s)
    counts=Counter()
    for i,(path,items) in enumerate(byfile.items()):
        if sha(path)!=items[0]['sha256']:raise ValueError('Frozen source changed')
        record=json.load(gzip.open(path,'rt'));games=list(record['unique_tables'].values()) if 'unique_tables' in record else [record]
        approved={s['trajectory']:s for s in items}
        actor_bots=items[0]['actor_bots']
        for game in games:
            b=Board.from_dict(game['board']);t=game['tables'][0]
            signature=digest([board_key(b),b.auction,[actor_bots[x] for x in game['assignments']],
                              [(x['seat'],x['card']) for x in t['actions']],t.get('declarer_tricks')])
            if signature not in approved:continue
            r=byboard[board_key(b)]
            if b.contract is None:continue
            slot=r['auction_outcomes'].setdefault(digest(list(b.auction)),dict(calls=list(b.auction),
                    contract=b.contract.text(),declarer=b.contract.declarer,tricks=[]))
            slot['tricks'].append(t['declarer_tricks']);counts['games']+=1
        if i%250==0:print(json.dumps(dict(source_files=i,total_files=len(byfile))),flush=True)
    a.out.mkdir(parents=True,exist_ok=True);atomic_json(a.out/'dataset.json',data)
    summary=json.load(open(a.source/'summary.json'));summary.update(exact_auction_matching=True,
        parent_dataset_sha256=sha(a.source/'dataset.json'),dataset_sha256=sha(a.out/'dataset.json'),
        exact_auctions=sum(len(r['auction_outcomes']) for r in byboard.values()),
        reward_note='Only identical auctions reuse historical play. Missing exact auctions are played with frozen clean Gen3.')
    atomic_json(a.out/'summary.json',summary);print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
