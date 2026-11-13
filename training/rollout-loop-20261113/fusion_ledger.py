#!/usr/bin/env python3
"""The fusion ledger: how often a bot's card gives away a contract that was guaranteed, counted against the exact
single-dummy solver and not against any opponent.

  SURE_BIN=/path/to/sure_cpp python training/rollout-loop-20261113/fusion_ledger.py RUN=DIR[,DIR...] [RUN=...] --out ledger.json

Why (Max, 13 November 11:16 UTC): Gen 8 and the nets trained on it carry strategy-fusion errors, so IMPs against Gen 8
need not rise as Stu sheds them. This count has no opponent in it. Each DIR holds a run's full records (`episodes/` of
scripts/x8_match.py --episodes); a run played in shards names all its folders. Every bot at the table is counted, the
outside opponent too (BEN included: its cards are in the records like anyone's).

Decisions counted: dummy down, at least two legal cards, at most --cards cards in the hand to play (default 7: the last
seven tricks), the contract neither made nor lost yet. The solver (bridge_harness/x8_claims.py) is asked as the engine
asks it, with --each seconds a question.

  declaring side to play
    held        some card guarantees the contract from the declaring side's own view: against every split of the cards
                it cannot see and every defence, given hand sizes and show-outs
    gave_up     of those, the card played does not guarantee it. This is the error the count is for: nothing about the
                hidden hands was needed to avoid it
  a defender to play, in the deal as it really lies
    choice      some legal card leaves declarer holding such a guarantee and another does not
    handed      of those, the card played leaves declarer holding it. A defender does not see declarer's hand, so this
                is not always an error from its seat; on the same deals it compares bots fairly
  unknown       the solver gave no answer in time (not counted above)

Counts are kept by bot and by contract class: `game` (games, slams and doubled contracts, where Stu's own logic keeps a
guarantee from ten cards on, so its gave_up there checks the ledger) and `part` (undoubled partscores, where that logic
is off). Only each board's two root tables are read.
"""
import argparse
import collections
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bridge_harness import x8_claims  # noqa: E402
from bridge_harness.core import Board, Game, card  # noqa: E402
from bridge_harness.x8_player import game_or_doubled, touching  # noqa: E402

KEYS = ('tables', 'decl_decisions', 'held', 'gave_up', 'decl_unknown', 'def_decisions', 'choice', 'handed', 'def_unknown')


def one(args):
    path, most, each = args
    finder = x8_claims.shared()
    finder.each = each
    with gzip.open(path, 'rt') as f:
        d = json.load(f)
    names = {'candidate': d['candidate'], 'opponent': d['opponent']}
    out = collections.Counter()
    for e in d['unique_tables'].values():
        if e.get('schema_version') == 'v4-passed-out-v1' or not e.get('tables'):
            continue
        board = Board.from_dict(e['board'])
        k = board.contract
        klass = 'game' if game_or_doubled(k) else 'part'
        game = Game(board)
        seen = set()
        for a in e['tables'][0]['actions']:
            o = game.observation()
            x = card(a['card'])
            bot = names.get(a['player'], a['player'])
            if (bot, klass) not in seen:
                seen.add((bot, klass))
                out[(bot, klass, 'tables')] += 1
            need = k.level + 6 - o.declarer_tricks
            if len(o.legal) > 1 and o.known_hands[k.dummy] is not None and len(o.known_hands[o.actor]) <= most \
                    and 0 < need <= 13 - len(o.history) // 4:
                if o.controller % 2 == k.declarer % 2:
                    out[(bot, klass, 'decl_decisions')] += 1
                    state, sure = finder.root(o)
                    if state == 'unknown':
                        out[(bot, klass, 'decl_unknown')] += 1
                    elif state == 'guaranteed':
                        out[(bot, klass, 'held')] += 1
                        out[(bot, klass, 'gave_up')] += not sure[x]
                else:
                    out[(bot, klass, 'def_decisions')] += 1
                    reps = [x if x in run else run[0] for run in touching(o)]
                    world = tuple(tuple(sorted(h)) for h in game.hands)
                    hand = finder.handovers(o, [world], reps, allowance=each * len(reps))[0]
                    if (hand < 0).any():
                        out[(bot, klass, 'def_unknown')] += 1
                    elif hand.min() != hand.max():
                        out[(bot, klass, 'choice')] += 1
                        out[(bot, klass, 'handed')] += int(hand[reps.index(x)] == 1)
            game.play(x)
    return dict(out)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('runs', nargs='+', help='NAME=DIR[,DIR...]: a run and its folders (each with episodes/)')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--cards', type=int, default=7)
    p.add_argument('--each', type=float, default=1.)
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--first', type=int, default=0, help='board indices from here')
    p.add_argument('--last', type=int, default=1 << 30, help='... to below here')
    a = p.parse_args()
    report = dict(what='fusion_ledger.py: see its docstring for each count', cards=a.cards, each=a.each, runs={})
    with ProcessPoolExecutor(a.workers) as pool:
        for item in a.runs:
            name, folders = item.split('=', 1)
            files = [f for folder in folders.split(',') for f in sorted((Path(folder) / 'episodes').glob('*.json.gz'))
                     if a.first <= int(f.name.split('.')[0]) < a.last]
            total = collections.Counter()
            for part in pool.map(one, [(f, a.cards, a.each) for f in files], chunksize=8):
                total.update(part)
            bots = {}
            for (bot, klass, key), v in sorted(total.items()):
                bots.setdefault(bot, {}).setdefault(klass, dict.fromkeys(KEYS, 0))[key] = int(v)
            for by in bots.values():
                by['all'] = {key: sum(c[key] for c in by.values()) for key in KEYS}
            report['runs'][name] = dict(boards=len(files), bots=bots)
            for bot, by in bots.items():
                c = by['all']
                print(f"{name:10s} {bot:12s} tables {c['tables']:4d} | declaring: held {c['held']:5d} gave up {c['gave_up']:4d} "
                      f"({100 * c['gave_up'] / max(c['held'], 1):.2f}%) | defending: choice {c['choice']:5d} handed {c['handed']:4d} "
                      f"({100 * c['handed'] / max(c['choice'], 1):.1f}%) | unknown {c['decl_unknown'] + c['def_unknown']}", flush=True)
    a.out.write_text(json.dumps(report, indent=1) + '\n')


if __name__ == '__main__':
    main()
