#!/usr/bin/env python3
"""Every gap fork after the opening lead in folders of self-play episodes, with the kind of every legal card at the
decision, the search's gap for each, the card played, the forced card and what it really cost.

  python scripts/plan_play_scan.py plays.pkl EPISODES_DIR [EPISODES_DIR ...]
"""
import gzip, json, sys, glob, pickle, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.core import card, Board, Game, winner

def kinds(o, hands, trump):
    """kind of each legal card at this decision (a short label)."""
    pos = len(o.trick)
    out = {}
    seat = o.actor
    left = set().union(*[set(h) for h in hands])              # every card still in a hand (the true deal)
    for x in o.legal:
        suit, rank = x // 13, x % 13
        hon = rank >= 9
        if pos == 0:
            master = not any(c // 13 == suit and c % 13 > rank for c in left if c not in hands[seat])
            n = sum(1 for c in hands[seat] if c // 13 == suit)
            if trump is not None and suit == trump:
                k = 'lead trump high' if master or hon else 'lead trump low'
            elif master:
                k = 'lead a winner'
            elif hon:
                k = 'lead an honour'
            elif n == 1:
                k = 'lead a singleton'
            elif any(c // 13 == suit and c % 13 >= 9 for c in hands[seat]):
                k = 'lead low from an honour'
            else:
                k = 'lead low from small'
        else:
            led = o.trick[0][1] // 13
            t = list(o.trick) + [(seat, x)]
            ahead = winner(t, trump) == seat
            partner_ahead = winner(list(o.trick), trump) == (seat + 2) % 4
            p = ('2nd', '3rd', '4th')[pos - 1]
            if suit == led:
                if ahead:
                    k = f'{p} follow, takes the trick so far' + (' over partner' if partner_ahead else '')
                else:
                    k = f'{p} follow, honour under' if hon else f'{p} follow low'
            elif trump is not None and suit == trump:
                k = f'{p} ruff' + (' partner\'s trick' if partner_ahead else '') if ahead else f'{p} underruff'
            else:
                k = f'{p} discard an honour' if hon else f'{p} discard low'
        out[x] = k
    return out

out, tables, t0 = [], 0, time.time()
for name in sys.argv[2:]:
    for n, f in enumerate(sorted(glob.glob(f'{name}/*.json.gz'))):
        try:
            d = json.load(gzip.open(f, 'rt'))
        except Exception:
            continue
        for key, e in d['unique_tables'].items():
            if 'tables' not in e or not e['tables'] or e['tables'][0].get('status', 'ok') != 'ok' or not e['tables'][0].get('actions'):
                continue
            tables += 1
            forks = sorted([g for g in e.get('gap_forks') or [] if g['ply'] > 0 and 'realized_cost_tricks' in g], key=lambda g: g['ply'])
            if not forks:
                continue
            board = Board.from_dict(e['board'])
            trump = board.contract.trump
            trump = None if trump is None or trump > 3 else trump
            acts = e['tables'][0]['actions']
            game, done = Game(board), 0
            for g in forks:
                ply = g['ply']
                if ply >= len(acts) or not acts[ply].get('gen6') or not acts[ply].get('estimates'):
                    continue
                while done < ply:
                    game.play(card(acts[done]['card'])); done += 1
                o = game.observation()
                a, b = card(acts[ply]['card']), card(g['forced_card'])
                if b not in o.legal or a == b:
                    continue
                kd = kinds(o, [tuple(h) for h in game.hands], trump)
                declaring = o.actor % 2 == board.contract.declarer % 2
                out.append(dict(set=Path(name).name, family=d['family'], ply=ply, trick=ply // 4 + 1, declaring=declaring, pos=len(o.trick),
                                played=a, forced=b, est=g['estimated_gap'], prop=g['propensity'], real=g['realized_cost_tricks'],
                                imps=g.get('realized_cost_imps') or 0, band=g['band'],
                                gaps={card(c): v['gap_to_best'] for c, v in acts[ply]['estimates'].items()}, kinds=kd))
        if n % 2000 == 0:
            print(name, n, tables, len(out), round(time.time() - t0), flush=True)
pickle.dump(dict(tables=tables, rows=out), open(sys.argv[1], 'wb'))
print('done', tables, len(out), round(time.time() - t0))
