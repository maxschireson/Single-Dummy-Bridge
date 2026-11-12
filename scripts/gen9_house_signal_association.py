"""G9-S6: association between the fact a signal would state and the house bots' high or low spot, per bot and signal.

For each signalling occasion (signal_experience.occasions with detail) under one scheme per key, P(high spot | first
message) - P(high spot | second message), with its standard error. Zero means the spot says nothing about the fact.
Run: python scripts/gen9_house_signal_association.py EPISODES_DIR [...] --out association.json [--bots ben,ben64]"""
import gzip, json, glob, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from collections import defaultdict
import numpy as np
from bridge_harness.core import Board
from bridge_harness.signal_experience import occasions, replay_plays
from bridge_harness.signals import SignalModel, MESSAGES
BASE = dict(length_lead_vs_suit='4th', length_lead_vs_nt='4th', attitude='standard', count='standard', signal_on_partner_lead='attitude',
            signal_on_declarer_lead='count', first_discard='attitude', trump_signal='count')
variants = {'att': BASE, 'cnt': dict(BASE, signal_on_partner_lead='count', first_discard='count'),
            'sp': dict(BASE, signal_on_partner_lead='suit_preference', signal_on_declarer_lead='suit_preference', first_discard='lavinthal')}
models = {k: SignalModel(v) for k, v in variants.items()}
OWNER = {'partner_lead.attitude': 'att', 'declarer_lead.count': 'att', 'first_discard.attitude': 'att', 'trump.count': 'att',
         'partner_lead.count': 'cnt', 'first_discard.count': 'cnt', 'partner_lead.suit_preference': 'sp',
         'declarer_lead.suit_preference': 'sp', 'first_discard.lavinthal': 'sp'}
tally = defaultdict(lambda: defaultdict(lambda: np.zeros(3)))   # (bot, key) -> message -> [high, low, mid]
import argparse
ap = argparse.ArgumentParser()
ap.add_argument('episodes', nargs='+')
ap.add_argument('--out', required=True)
ap.add_argument('--bots', default='', help='comma-separated bot ids to keep (default: all)')
args = ap.parse_args()
keep = set(filter(None, args.bots.split(',')))
for path in sorted(f for d in args.episodes for f in glob.glob(str(Path(d) / '*.json.gz'))):
    e = json.load(gzip.open(path, 'rt'))
    for r in e['unique_tables'].values():
        b = Board.from_dict(r['board'])
        main = [t for t in r['tables'] if t.get('depth', 0) == 0]
        if b.contract is None or not main: continue
        acts = main[0]['actions']; plays = replay_plays(b, acts); side = 1 - b.contract.declarer % 2
        roles = {a['player'] for a in acts if 'NESW'.index(a['seat']) % 2 == side}
        if len(roles) != 1: continue
        bot = e.get(roles.pop())
        if keep and bot not in keep: continue
        seen = set()
        for name, m in models.items():
            for key, n, s, hit, msg, where in occasions(b, plays, m, side, detail=True):
                if msg < 0 or OWNER.get(key) != name: continue
                tally[(bot, key)][msg][['high', 'low', 'mid'].index(where)] += 1
out = {}
for (bot, key), by in sorted(tally.items()):
    if key.endswith('.none') or key.startswith('lead'): continue
    kind = key.split('.')[-1]
    a, b_ = by.get(0, np.zeros(3)), by.get(1, np.zeros(3))
    if a.sum() < 20 or b_.sum() < 20: continue
    ph0, ph1 = a[0] / a.sum(), b_[0] / b_.sum()
    se = np.sqrt(ph0 * (1 - ph0) / a.sum() + ph1 * (1 - ph1) / b_.sum())
    mid = (a[2] + b_[2]) / (a.sum() + b_.sum())
    out[f'{bot}|{key}'] = dict(n=int(a.sum() + b_.sum()), high_given_first=round(ph0, 3), high_given_second=round(ph1, 3), association=round(ph0 - ph1, 3), se=round(se, 3), mid_share=round(mid, 3))
    print(f'{bot:>6} {key:>30} n={int(a.sum()+b_.sum()):5d}  P(high|{MESSAGES[kind][0]})={ph0:.2f}  P(high|{MESSAGES[kind][1]})={ph1:.2f}  diff={ph0-ph1:+.3f} ± {se:.3f}  mid={mid:.2f}')
json.dump(out, open(args.out, 'w'), indent=1)
