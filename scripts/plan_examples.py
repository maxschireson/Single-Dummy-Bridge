#!/usr/bin/env python3
"""Print the fork pairs on which the ceiling's playouts disagree most clearly with the search.

  python scripts/plan_examples.py ceiling.json b_better 8 --episodes DIR
  python scripts/plan_examples.py ceiling.json a_better 8 --episodes DIR

`b_better`: pairs with a recorded gap up to 0.5 where the real bots' playouts put the other card ahead by more than
two standard errors (most ahead first). `a_better`: pairs with a recorded gap up to 0.25 where real play makes the
bot's own card better than double dummy says by more than 0.3. For each: contract, auction, the four hands as dealt
and as they stand, the play so far, double-dummy and played-out results layout by layout, and how the two real
tables went on. The deal is shown in full: a reading aid for a person, nothing a player sees.
"""
import glob
import gzip
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.core import SEATS, Board, Game, card, symbol
rows=[r for r in json.load(open(sys.argv[1]))['rows'] if r['band']>=0 and len(r['worlds']['roll'])>=12]
episodes = sys.argv[sys.argv.index('--episodes') + 1]
wanted = {r['family'] for r in rows}
fam2file = {}
for f in glob.glob(episodes + '/*.json.gz'):
    family = json.load(gzip.open(f, 'rt'))['family']
    if family in wanted:
        fam2file[family] = f
def hand_str(cards):
    out=[]
    for s in range(4):
        out.append(''.join('23456789TJQKA'[c%13] for c in sorted([c for c in cards if c//13==s], reverse=True)) or '-')
    return '.'.join(out)
sel=[]
for r in rows:
    roll=np.array(r['worlds']['roll']); dd=np.array(r['worlds']['dd'])
    d=(roll[:,0]-roll[:,1]); t=d.mean(); se=d.std(ddof=1)/np.sqrt(len(d)); c=(d-(dd[:,0]-dd[:,1])).mean()
    r['_t']=t; r['_se']=se; r['_c']=c; r['_dd']=(dd[:,0]-dd[:,1]).mean()
which=sys.argv[2]
if which=='b_better': sel=sorted([r for r in rows if r['estimated']<=0.5 and r['_t']/max(r['_se'],.05)<-2.0], key=lambda r:r['_t'])[:int(sys.argv[3])]
else: sel=sorted([r for r in rows if r['estimated']<=0.25 and r['_c']>0.3], key=lambda r:-r['_c'])[:int(sys.argv[3])]
SUITS='SHDC'
for r in sel:
    d=json.load(gzip.open(fam2file[r['family']],'rt')); e=d['unique_tables'][r['table']]
    board=Board.from_dict(e['board']); root=e['tables'][r['table_a']]; fork=e['tables'][r['table_b']]
    ply=r['ply']; a=root['actions'][ply]['card']; b=fork['actions'][ply]['card']
    g=Game(board)
    for x in root['actions'][:ply]: g.play(card(x['card']))
    o=g.observation()
    c=board.contract
    print(f"\n=== {e['board']['contract']} by {e['board']['declarer']}, trick {r['trick']}, {SEATS[o.actor]} to play ({'declaring side' if r['declaring'] else 'defending'}); Gen 6 played {a}, other card {b}. Recorded gap {r['estimated']:.3f}; fresh double dummy {r['_dd']:+.2f}; real Gen 6 playouts {r['_t']:+.2f} +- {r['_se']:.2f} (B better when negative); on the real deal B cost {r['final']:+d}")
    print('   auction:', ' '.join(e['board']['auction']))
    hands=[hand_str(h) for h in g.hands]
    orig=e['board']['hands']
    print('   original  N', orig[0], ' E', orig[1], ' S', orig[2], ' W', orig[3])
    print('   now       N', hands[0], ' E', hands[1], ' S', hands[2], ' W', hands[3])
    plays=[x['card'] for x in root['actions'][:ply]]
    tricks=[' '.join(plays[i:i+4]) for i in range(0,len(plays),4)]
    lead=root['actions'][0]['seat']
    print('   play so far (first card by', lead+'):', ' | '.join(tricks))
    roll=np.array(r['worlds']['roll']); dd=np.array(r['worlds']['dd'])
    print('   per layout, decider tricks A/B: double dummy', ' '.join(f"{int(x[0])}/{int(x[1])}" for x in dd.tolist()))
    print('                                   real play   ', ' '.join(f"{int(x[0])}/{int(x[1])}" for x in roll.tolist()))
    cont_a=' '.join(x['card'] for x in root['actions'][ply:ply+8]); cont_b=' '.join(x['card'] for x in fork['actions'][ply:ply+8])
    print('   real table went on:', cont_a, '... declarer took', root['declarer_tricks'], '| after', b+':', cont_b, '... declarer took', fork['declarer_tricks'])
