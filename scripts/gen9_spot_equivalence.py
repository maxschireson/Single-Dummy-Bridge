#!/usr/bin/env python3
"""E9-3: how often are the spot cards (nine and below) of the suit played not equivalent?

Gen 9 work in progress (sam, signals). For every card played on the main table of recorded boards
(forks are skipped), when the player held two or more spots ranked nine or below in the suit of
the card played, the true position is solved by DDS before the card is played and the spots'
double-dummy values are compared. A decision is "split" when those spots do not all take the
same number of tricks; its cost is the best spot's value minus the worst's, in tricks.

Also recorded, from the bot's own record of the decision: whether the search's set of exactly
tied cards (`proposal_probabilities`, else `behavior_probabilities`) held every spot of the
class, and whether the card played was itself a spot. That says how the class rule relates to
the ties a carding bot chooses among.

  python scripts/gen9_spot_equivalence.py EPISODES_DIR [EPISODES_DIR ...] --out rows.jsonl --decisions 8000

Kind of evidence: double-dummy proxy on the true deal.
"""
import os
for _name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_name, '1')
import argparse
from concurrent.futures import ProcessPoolExecutor
import glob
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.core import Board, Game, card, symbol  # noqa: E402
from bridge_harness.dds import DDS  # noqa: E402

SPOT = 7            # rank index of the nine: ranks 0..7 are the deuce to the nine
STATE = {}


def situation(i, seat, c, history, contract):
    """Public description of play i: lead, follow or discard; and whose card led the trick."""
    start = i - i % 4
    if i == start:
        return 'opening_lead' if i == 0 else 'lead'
    led_seat, led = history[start]
    if c // 13 != led // 13:
        return 'discard' if contract.trump == 4 or c // 13 != contract.trump else 'ruff'
    partner = (seat + 2) % 4
    if led_seat == partner:
        return 'follow_partner'
    return 'follow_opponent'


def episode_rows(path, limit_tables=10 ** 9):
    if 'dds' not in STATE:
        STATE['dds'] = DDS()
    dds = STATE['dds']
    with gzip.open(path, 'rt') as f:
        episode = json.load(f)
    rows = []
    for key, record in episode['unique_tables'].items():
        board = Board.from_dict(record['board'])
        c = board.contract
        if c is None:
            continue
        for t in record['tables']:
            if t.get('depth', 0) != 0:          # the main table only; forks repeat its opening
                continue
            game = Game(board)
            for a in t['actions']:
                if game.done:
                    break
                o = game.observation()
                x = card(a['card'])
                i = len(game.history)
                seat = o.actor
                suit = x // 13
                in_suit = [y for y in o.legal if y // 13 == suit]
                spots = [y for y in in_suit if y % 13 <= SPOT]
                if len(spots) >= 2:
                    values, _ = dds.solve([tuple(sorted(h)) for h in game.hands], c.trump, game.leader, tuple(game.trick))
                    v = [values[y] for y in spots]
                    tied = a.get('proposal_probabilities') or a.get('behavior_probabilities') or {}
                    tied = {card(k) for k, p in tied.items() if p > 0} if isinstance(tied, dict) else set()
                    role = 'declarer' if seat == c.declarer else 'dummy' if seat == c.dummy else 'defender'
                    left = 13 - sum(1 for _, y in game.history if y // 13 == suit)
                    gone = {y for _, y in game.history} | set(o.legal)
                    higher_out = sum(1 for r in range(max(y % 13 for y in spots) + 1, 13) if suit * 13 + r not in gone)
                    est = a.get('estimates') or {}
                    gaps = [est.get(symbol(y), {}).get('gap_to_best') for y in spots] if isinstance(est, dict) else []
                    gaps = [g for g in gaps if g is not None]
                    rows.append(dict(
                        episode=Path(path).name, table=key, ply=i, trick=i // 4 + 1, role=role,
                        situation=situation(i, seat, x, game.history, c), trump=c.trump, side_suit=suit != c.trump,
                        strain='nt' if c.trump == 4 else 'suit', n_spots=len(spots), top_spot=max(y % 13 for y in spots) + 2,
                        n_in_suit=len(in_suit), left_in_suit=left, higher_out=higher_out, played_spot=x % 13 <= SPOT,
                        search_spread=(max(gaps) - min(gaps)) if len(gaps) == len(spots) else None,
                        split=len(set(v)) > 1, cost=max(v) - min(v),
                        lowest_is_best=values[min(spots)] == max(v), highest_is_best=values[max(spots)] == max(v),
                        tied_known=bool(tied), tied_has_all=bool(tied) and set(spots) <= tied,
                        tied_spots=len(tied & set(spots)) if tied else None))
                game.play(x)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('episodes', nargs='+')
    ap.add_argument('--out', required=True)
    ap.add_argument('--decisions', type=int, default=8000, help='stop after this many defender decisions')
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--stride', type=int, default=1, help='use every k-th episode file (spreads the sample over the run)')
    args = ap.parse_args()
    files = sorted(f for d in args.episodes for f in glob.glob(str(Path(d) / '*.json.gz')))[::args.stride]
    done = defender = 0
    pending = iter(files)
    with open(args.out, 'w') as out, ProcessPoolExecutor(args.workers) as pool:
        flight = [pool.submit(episode_rows, f) for f in [next(pending, None) for _ in range(2 * args.workers)] if f]
        while flight:
            rows = flight.pop(0).result()
            for r in rows:
                out.write(json.dumps(r) + '\n')
            done += 1
            defender += sum(r['role'] == 'defender' for r in rows)
            if done % 20 == 0:
                print(f'{done} files, {defender} defender decisions', flush=True)
            nxt = next(pending, None) if defender < args.decisions else None
            if nxt:
                flight.append(pool.submit(episode_rows, nxt))
    print(f'{done} files, {defender} defender decisions', flush=True)


if __name__ == '__main__':
    main()
