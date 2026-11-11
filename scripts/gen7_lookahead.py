#!/usr/bin/env python3
"""What looking ahead could be worth, from gap forks and root tables (docs/gen7_data_capture_2026-11-11.md).

  python scripts/gen7_lookahead.py --episodes DIR [--limit N] [--out result.json]

Three tables, by the trick of the decision:

  lost      Double-dummy cost, on the real deal, of each card a Gen 6 seat played in a root table.
            The ceiling on any improvement: it includes what cannot be avoided without seeing the cards.
  estimate  Gap forks. A is the card Gen 6 played, B a card it rated `estimated_gap` tricks worse and
            which the collector then forced and played out. Estimated gap against the realized cost of B.
  ahead     The same pairs. Both lines valued double dummy on the real deal straight after the card and
            after 4, 8 and 12 plies of the play that actually followed, against how the hands finished.
            `error` is the root-mean-square difference from the final result; `regret` is the tricks lost
            by choosing between A and B on that value (ties go to A); `correlation` and `slope` are of
            the final difference on that value. Depth 0 is the double-dummy assumption with the layout
            known; deeper rows are that assumption postponed by real play. Part of every error is the
            chance in how two lines happen to finish, which no evaluation can predict, and the deeper
            rows have seen some of that chance already. They bound what a search of that depth could
            do; they do not measure it. To measure a search, run it on these same pairs and average
            the realized cost of B over the pairs where it prefers B.

Gap forks are sampled by band, not in proportion to how often such cards arise, so `estimate` and
`ahead` describe the sampled pairs and are reported by band.
"""
import argparse
import gzip
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.core import SEATS, Board, Game, card
from bridge_harness.players import PIMCPlayer

DEPTHS = (0, 4, 8, 12)
GEN6 = ('6-32', '6-256')


def phase(ply):
    trick = ply // 4 + 1
    return 'lead' if ply == 0 else 'trick 1' if trick == 1 else 'trick 2' if trick == 2 else 'tricks 3-4' if trick <= 4 \
        else 'tricks 5-6' if trick <= 6 else 'tricks 7-9' if trick <= 9 else 'tricks 10-13'


PHASES = ('lead', 'trick 1', 'trick 2', 'tricks 3-4', 'tricks 5-6', 'tricks 7-9', 'tricks 10-13')


class Solver:
    def __init__(self):
        self.dds = PIMCPlayer(samples=1, objective='tricks').dds

    def values(self, game):
        """Declarer's final tricks, double dummy on the real deal, after each legal card of the seat to play."""
        o = game.observation()
        hands = tuple(tuple(sorted(h)) for h in game.hands)
        values, _ = self.dds.solve_batch([hands], o.contract.trump, o.leader, o.trick, fixed_seats=(0, 1, 2, 3))[0]
        declaring = o.actor % 2 == o.contract.declarer % 2
        remaining = 13 - len(o.history) // 4
        return {c: o.declarer_tricks + (t if declaring else remaining - t) for c, t in values.items()}, declaring

    def value(self, game):
        """Declarer's final tricks with double-dummy play from here."""
        if game.done:
            return game.declarer_tricks
        values, declaring = self.values(game)
        return max(values.values()) if declaring else min(values.values())


    def line(self, board, actions, ply):
        """Declarer's double-dummy tricks on the real deal after the card at `ply` and after each further depth of the recorded play."""
        game = Game(board)
        done, out = 0, []
        for depth in DEPTHS:
            for a in actions[done:ply + 1 + depth]:
                game.play(card(a['card']))
            done = max(done, min(len(actions), ply + 1 + depth))
            out.append(self.value(game))
        return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--episodes', type=Path, required=True)
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--lost-tables', type=int, default=400)
    p.add_argument('--out')
    a = p.parse_args()
    solver = Solver()
    files = sorted(a.episodes.glob('*.json.gz'))
    lost, pairs, episodes, lost_tables, tables_with_forks = {}, [], 0, 0, 0
    for path in files:
        with gzip.open(path, 'rt') as f:
            d = json.load(f)
        records = [e for e in d['unique_tables'].values() if e.get('gap_forks')]
        if not records:
            continue
        episodes += 1
        if a.limit and episodes > a.limit:
            break
        who = {'candidate': d['candidate'], 'opponent': d['opponent']}
        for e in records:
            tables_with_forks += 1
            board = Board.from_dict(e['board'])
            declarer = board.contract.declarer
            root = e['tables'][0]
            if lost_tables < a.lost_tables:          # 1. double-dummy cost of each card a Gen 6 seat played
                lost_tables += 1
                game = Game(board)
                for act in root['actions']:
                    c = card(act['card'])
                    if who.get(act['player']) in GEN6 and act.get('estimates') and not game.done:
                        values, declaring = solver.values(game)
                        best = max(values.values()) if declaring else min(values.values())
                        x = lost.setdefault(phase(act['ply']), [0, 0.])
                        x[0] += 1
                        x[1] += abs(best - values[c])
                    game.play(c)
            for g in e['gap_forks']:                 # 2 and 3. the forked pairs
                fork = e['tables'][g['fork_table']]
                ply = g['ply']
                seat = SEATS.index(root['actions'][ply]['seat'])
                sign = 1 if seat % 2 == declarer % 2 else -1          # the decider's side, in declarer's tricks
                final = sign * (root['declarer_tricks'] - fork['declarer_tricks'])      # realized cost of B to the decider
                if final != g['realized_cost_tricks']:
                    raise ValueError('Recorded realized cost disagrees with the two tables')
                row = dict(phase=phase(ply), band=g['band'], estimated=g['estimated_gap'], final=final, family=d['family'],
                           ply=ply, propensity=g['propensity'])
                line_a, line_b = solver.line(board, root['actions'], ply), solver.line(board, fork['actions'], ply)
                for depth, x, y in zip(DEPTHS, line_a, line_b):
                    row[f'd{depth}'] = sign * (x - y)
                pairs.append(row)

    def summary(rows):
        f = np.array([r['final'] for r in rows], float)
        out = dict(pairs=len(rows), estimated_gap=round(float(np.mean([r['estimated'] for r in rows])), 3),
                   realized_cost=round(float(f.mean()), 3), realized_se=round(float(f.std(ddof=1) / math.sqrt(len(f))), 3) if len(f) > 1 else None,
                   b_did_better=round(float((f < 0).mean()), 3), b_did_worse=round(float((f > 0).mean()), 3),
                   regret_always_a=round(float(np.maximum(0, -f).mean()), 4),
                   estimate_error=round(float(np.sqrt(np.mean((np.array([r['estimated'] for r in rows]) - f) ** 2))), 3))
        for depth in DEPTHS:
            v = np.array([r[f'd{depth}'] for r in rows], float)
            pick_b = v < 0                                             # B looks better at this depth
            regret = np.where(pick_b, np.maximum(0, f), np.maximum(0, -f))
            spread = v.std() > 0 and f.std() > 0
            out[f'ahead_{depth}'] = dict(error=round(float(np.sqrt(np.mean((v - f) ** 2))), 3), regret=round(float(regret.mean()), 4),
                                         same_sign=round(float((np.sign(v) == np.sign(f)).mean()), 3), mean=round(float(v.mean()), 3),
                                         correlation=round(float(np.corrcoef(v, f)[0, 1]), 3) if spread else None,
                                         slope=round(float(np.polyfit(v, f, 1)[0]), 3) if spread else None)
        return out

    result = dict(episodes=min(episodes, a.limit or episodes), pairs=len(pairs), depths=DEPTHS, root_tables_with_gap_forks=tables_with_forks,
                  lost={k: dict(decisions=lost[k][0], dd_cost=round(lost[k][1] / lost[k][0], 4)) for k in PHASES if k in lost},
                  by_phase={k: summary([r for r in pairs if r['phase'] == k]) for k in PHASES if any(r['phase'] == k for r in pairs)},
                  by_band={str(b): summary([r for r in pairs if r['band'] == b]) for b in sorted({r['band'] for r in pairs})},
                  by_phase_and_band={f'{k} band {b}': summary(sub) for k in PHASES for b in sorted({r['band'] for r in pairs})
                                     for sub in [[r for r in pairs if r['phase'] == k and r['band'] == b]] if len(sub) >= 30},
                  all=summary(pairs) if pairs else None)
    if a.out:
        Path(a.out).write_text(json.dumps(dict(result, rows=pairs), indent=1))
    print(json.dumps(result, indent=1))


if __name__ == '__main__':
    main()
