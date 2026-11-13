#!/usr/bin/env python3
"""Every Gen 6 opening lead in folders of self-play episodes: the leader's hand, the search's gap for each legal card,
and the lead forks (forced lead, recorded gap, draw probability, what it really cost on the true deal).

  python scripts/plan_lead_scan.py leads.pkl EPISODES_DIR [EPISODES_DIR ...]
"""
import gzip, json, sys, glob, pickle, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.core import card, Board
out, t = [], time.time()
for name in sys.argv[2:]:
    files = sorted(glob.glob(f'{name}/*.json.gz'))
    for n, f in enumerate(files):
        try:
            d = json.load(gzip.open(f, 'rt'))
        except Exception:
            continue
        for key, e in d['unique_tables'].items():
            if 'tables' not in e or not e['tables'] or e['tables'][0].get('status', 'ok') != 'ok' or not e['tables'][0].get('actions'):
                continue
            a = e['tables'][0]['actions'][0]
            if a.get('ply') != 0 or not a.get('gen6') or not a.get('estimates'):
                continue
            board = Board.from_dict(e['board'])
            seat = 'NESW'.index(a['seat'])
            forks = [(card(g['forced_card']), g['estimated_gap'], g['propensity'], g['realized_cost_tricks'], g.get('realized_cost_imps') or 0, g['band'])
                     for g in e.get('gap_forks') or [] if g['ply'] == 0 and 'realized_cost_tricks' in g]
            out.append(dict(set=Path(name).name, family=d['family'], hand=list(board.hands[seat]), trump=board.contract.trump, level=board.contract.level,
                            declarer=board.contract.declarer, seat=seat, played=card(a['card']),
                            gaps={card(c): v['gap_to_best'] for c, v in a['estimates'].items()}, forks=forks,
                            dummy=list(board.hands[(board.contract.declarer + 2) % 4])))
        if n % 2000 == 0:
            print(name, n, len(out), round(time.time() - t), flush=True)
pickle.dump(out, open(sys.argv[1], 'wb'))
print('done', len(out), sum(len(o['forks']) for o in out), round(time.time() - t))
