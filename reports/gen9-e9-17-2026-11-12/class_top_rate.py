"""E9-17, sam's check: how often a stand-in's spot in the four first-round situations is the highest of its class.

    python reports/gen9-e9-17-2026-11-12/class_top_rate.py RUN/episodes t-high

P(highest) = hits under standard count + hits under upside-down count (each prescribes the highest for one message)."""
import sys, glob, gzip, json
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bridge_harness.core import Board
from bridge_harness.signal_experience import occasions, replay_plays
from bridge_harness.signals import SignalModel
base = dict(signal_on_partner_lead='count', signal_on_declarer_lead='count', first_discard='count', trump_signal='count')
models = {'std': SignalModel(dict(base, count='standard')), 'ud': SignalModel(dict(base, count='upside_down'))}
tally = defaultdict(lambda: [0, 0, 0.])
for path in sorted(glob.glob(sys.argv[1] + '/*.json.gz')):
    ep = json.load(gzip.open(path, 'rt'))
    for rec in ep['unique_tables'].values():
        board = Board.from_dict(rec['board'])
        mains = [t for t in rec['tables'] if t.get('depth', 0) == 0]
        if board.contract is None or not mains:
            continue
        acts = mains[0]['actions']; plays = replay_plays(board, acts)
        side = 1 - board.contract.declarer % 2
        roles = {a['player'] for a in acts if 'NESW'.index(a['seat']) % 2 == side}
        if len(roles) != 1:
            continue
        bot = ep.get(roles.pop(), '?')
        if bot != sys.argv[2]:
            continue
        for name, m in models.items():
            for key, n, s, hit in occasions(board, plays, m, side, None):
                t = tally[(name, key)]; t[0] += hit; t[1] += 1; t[2] += (n >= 3)
keys = sorted({k for _, k in tally})
for k in keys:
    a, b = tally[('std', k)], tally[('ud', k)]
    print(f"{k:>24} occasions={a[1]:5d} P(highest of class)={(a[0] + b[0]) / a[1]:.3f} share with 3+ spots={a[2] / a[1]:.3f}")
tot = [sum(tally[('std', k)][0] + tally[('ud', k)][0] for k in keys), sum(tally[('std', k)][1] for k in keys)]
print('all', tot[1], round(tot[0] / tot[1], 3))
