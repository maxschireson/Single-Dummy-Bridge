"""E9-24 positions: declarer-side decisions on NATIVE tables of the Gen 8 feeds that seat 8c-32 (g9, Gen 9).

Wraps experiments/sure_tricks/cells/arena_positions.positions and adds who defended. Writes positions where 8c-32
(the Precision rule bidder) defends, and the control: positions on the same boards where house bots defend.

usage: python3 -I e924_positions.py CELLS_DIR OUT.jsonl CARDS[,CARDS] SHARD.json [SHARD.json ...]
"""
import json
import sys

sys.path.insert(0, sys.argv[1])
import arena_positions as ap  # noqa: E402

out, wanted, files = sys.argv[2], {int(x) for x in sys.argv[3].split(',')}, sys.argv[4:]
seen, n, kinds = set(), 0, {}
with open(out, 'w') as f:
    for fn in files:
        for b in json.load(open(fn)).values():
            own = (b.get('conditions') or {}).get('own')
            if not own:
                continue
            for t in own['tables']:
                names = [x if isinstance(x, str) else str(x) for x in t.get('assignments') or []]
                if '8c-32' not in names:
                    continue
                key = (b['board']['id'], t['contract'], t['declarer'], tuple(t['plays']))
                if key in seen:
                    continue
                seen.add(key)
                for p in ap.positions(b['board'], t, wanted):
                    defenders = sorted({names[p['e_real']], names[p['w_real']]})
                    p['defenders'] = defenders
                    p['kind'] = 'precision_defends' if defenders == ['8c-32'] else ('house_defends' if '8c-32' not in defenders else 'mixed')
                    p['table'] = len(seen) - 1
                    p['source_file'] = fn.split('/')[0][:10]
                    f.write(json.dumps(p) + '\n')
                    n += 1
                    kinds[(p['kind'], p['cards'])] = kinds.get((p['kind'], p['cards']), 0) + 1
print(len(seen), 'native tables with 8c-32,', n, 'positions', kinds)
