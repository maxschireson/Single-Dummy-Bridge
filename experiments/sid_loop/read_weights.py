"""How much do the labels depend on the weights that pick a card's line? Scorer weights against weights that also
read the play.

  python read_weights.py EPISODES_DIR OUT.jsonl --cells BIN --scorer hand_fit_v0.npz --net ROLLOUT_NET.npz
                         [--cards 7] [--limit N] [--per-episode 2] [--play-weight 1.0] [--play-floor 0.05]

SPEC.md Part A labels `cert`, `floor` and `ceil` with the hand-fit scorer's weights (the auction only) for records
that carry no layouts. A bot at the table weighs its layouts by the play as well (Gen7Player.play_log_likelihood:
each hidden seat's past plays, the net's probability of the card played given what that seat saw in the layout, mixed
with `play_floor` of uniform, to the power `play_weight`; the Gen 8 bots use 1.0 and 0.05). This script labels the
same declaring-side decisions twice, once with each weighting, and writes one line per decision with both answers:

  positions   in each root table of an episode, the first decision of the declaring side with exactly --cards cards
              and more than one run of legal cards, the three targets asked where they are still open
  both ways   per card and target: guar (weight-free), single (weight-free), cert, floor, ceil; the best-floor card
  also        the true layout's weight relative to the mean layout under each weighting, and the effective number of
              layouts

Every card-fit layout is scored by the net (the bots resample a long list to 1,024 first). Research: nothing here is
played, and the reading net has seen these deals if they are in its training set.
"""
import argparse
import gzip
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sidlabel as S                                                        # noqa: E402
from bridge_harness.core import Board, Game, card                          # noqa: E402
from bridge_harness.gen6_nets import FitScorer                             # noqa: E402
from bridge_harness.gen7 import hidden_plays, past_view                    # noqa: E402
from bridge_harness.gen7_net import INPUTS, PolicyNet                      # noqa: E402

SUITMASK = np.zeros((4, 52), bool)
for _s in range(4):
    SUITMASK[_s, 13 * _s:13 * _s + 13] = True


class ReadWeights(S.Weights):
    """Scorer weights times the net's reading of the defenders' plays. `context` = (the declaring side's Observation,
    the defenders' bot, the declaring side's bot) is set before each position."""

    def __init__(self, scorer, net, play_weight, play_floor):
        super().__init__(scorer)
        self.net, self.play_weight, self.play_floor = net, play_weight, play_floor
        self.context = None
        self.rows = 0
        self.last = {}

    def cells(self, pos, who):
        o, defenders, declarers = self.context
        pool, east, logw = self.layouts(pos, who)
        e_real = who[0]
        fit = np.zeros(len(east))
        plays = hidden_plays(o, True)
        self.net.who = (defenders, declarers)
        for i, seat, chooser in plays:
            played = o.history[i][1]
            held = np.zeros((len(east), 52), bool)
            held[:, pool] = east if chooser == e_real else ~east
            held[:, [x for s, x in o.history[i:] if s == chooser]] = True
            base = self.net.encode(past_view(o, i))
            batch = {k: np.broadcast_to(base[k], (len(east), *base[k].shape)) for k in INPUTS}
            state = batch['state'].copy()
            state[held] = 1
            batch['state'] = state
            if i % 4:
                in_suit = held & SUITMASK[o.history[i - i % 4][1] // 13]
                legal = np.where(in_suit.any(axis=1)[:, None], in_suit, held)
            else:
                legal = held
            batch['legal'] = legal
            if not legal[:, played].all():
                raise RuntimeError('a listed layout makes an observed play illegal')
            count = legal.sum(axis=1)
            choice = count > 1
            if choice.any():
                logp = self.net.log_policy_arrays({k: batch[k][choice] for k in INPUTS})[:, played].astype(np.float64)
                fit[choice] += np.log((1 - self.play_floor) * np.exp(logp) + self.play_floor / count[choice])
                self.rows += int(choice.sum())
        both = logw + self.play_weight * fit
        self.last = dict(plays=len(plays), layouts=len(east), pool=pool, east=east, logw_scorer=logw, logw_read=both)
        return self.by_cell(pool, east, both), len(east)


def relative(pool, east, logw, true_east):
    """(the true layout's weight over the mean layout's, the effective number of layouts)."""
    w = np.exp(logw - logw.max())
    w /= w.sum()
    row = np.array([(true_east >> c) & 1 for c in pool], bool)
    hit = np.flatnonzero((east == row).all(axis=1))
    return (float(w[hit[0]] * len(w)) if len(hit) else None), float(1. / (w ** 2).sum())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('episodes', type=Path)
    p.add_argument('out', type=Path)
    p.add_argument('--cells', required=True)
    p.add_argument('--scorer', required=True)
    p.add_argument('--net', required=True)
    p.add_argument('--cards', type=int, default=7)
    p.add_argument('--limit', type=int, default=0, help='episodes')
    p.add_argument('--per-episode', type=int, default=2, help='positions an episode at most')
    p.add_argument('--play-weight', type=float, default=1.)
    p.add_argument('--play-floor', type=float, default=.05)
    p.add_argument('--seconds', type=float, default=0., help='stop after this long (the run resumes)')
    a = p.parse_args()
    done = set()
    if a.out.exists():
        done = {json.loads(line)['episode'] for line in open(a.out)}
    scorer = FitScorer(a.scorer)
    net = PolicyNet(a.net, scorer)
    A = S.Labeller(a.cells, a.scorer, cards=a.cards, full=True)
    B = S.Labeller(a.cells, a.scorer, cards=a.cards, full=True)
    B.weights = ReadWeights(scorer, net, a.play_weight, a.play_floor)
    files = sorted(a.episodes.glob('*.json.gz'))
    if a.limit:
        files = files[:a.limit]
    started = time.time()
    with open(a.out, 'a') as out:
        for f in files:
            name = f.name[:-len('.json.gz')]
            if name in done:
                continue
            if a.seconds and time.time() - started > a.seconds:
                break
            d = json.load(gzip.open(f, 'rt'))
            who = {'candidate': d['candidate'], 'opponent': d['opponent']}
            other = {'candidate': d['opponent'], 'opponent': d['candidate']}
            A.sv.reset()
            B.sv.reset()
            found = 0
            for ei, e in enumerate(d['unique_tables'].values()):
                if e.get('schema_version') == 'v4-passed-out-v1' or found >= a.per_episode:
                    continue
                board = Board.from_dict(e['board'])
                c = board.contract
                side = c.declarer % 2
                A.memo, B.memo = {}, {}
                for ti, table in enumerate(e['tables']):
                    if table.get('depth', 0) != 0 or found >= a.per_episode:
                        continue
                    game = Game(board)
                    for ai, act in enumerate(table['actions']):
                        x = card(act['card'])
                        actor = game.actor
                        hand = game.hands[actor]
                        if actor % 2 == side and len(hand) == a.cards and not game.done:
                            o = game.observation()
                            live = S.mask(y for h in game.hands for y in h) | S.mask(y for _, y in game.trick)
                            groups = S.runs(sorted(o.legal), S.mask(hand), live)
                            need = [c.level + 6 + j - game.declarer_tricks for j in S.TARGETS]
                            ask = sorted({nd for nd in need if 0 < nd <= len(hand)})
                            if len(groups) > 1 and ask:
                                voids = A.show_outs(game.history)
                                pos, east = A.view(board, game.hands, game.trick, game.leader, voids)
                                w = A.who(board, game.history)
                                t0 = time.time()
                                ga = A.solve(pos, east, w, ask, True)
                                B.weights.context = (o, who.get(act['player'], '') and other.get(act['player'], ''), who.get(act['player'], ''))
                                B.weights.last = {}
                                gb = B.solve(pos, east, w, ask, True)
                                last = B.weights.last
                                rec = dict(episode=name, entry=ei, table=ti, action=ai, contract=c.text(), cards=a.cards, need=need,
                                           declarer_bot=who.get(act['player'], ''), defender_bot=other.get(act['player'], ''),
                                           made=bool(table['declarer_tricks'] >= c.level + 6), played=int(x), reps=[g[0] for g in groups],
                                           seconds=round(time.time() - t0, 2), targets={})
                                if last:
                                    rs, es = relative(last['pool'], last['east'], last['logw_scorer'], east)
                                    rr, er = relative(last['pool'], last['east'], last['logw_read'], east)
                                    rec.update(plays=last['plays'], layouts=last['layouts'], true_rel_scorer=rs, true_rel_read=rr,
                                               effective_scorer=round(es, 1), effective_read=round(er, 1))
                                for nd in ask:
                                    one = {}
                                    for tag, got in (('scorer', ga[nd]), ('read', gb[nd])):
                                        one[tag] = dict(guar=got['guar'], single=got['single'], cert=got['cert'],
                                                        floor={k: (None if v is None else round(v, 5)) for k, v in got['floor'].items()},
                                                        ceil={k: (None if v is None else round(v, 5)) for k, v in got['ceil'].items()},
                                                        best=got['best'], best_floor=round(got['best_floor'], 5), best_cert=got['best_cert'])
                                    rec['targets'][str(nd)] = one
                                out.write(json.dumps(rec) + '\n')
                                out.flush()
                                found += 1
                                break
                        game.play(x)
            if not found:
                out.write(json.dumps(dict(episode=name, none=True)) + '\n')
                out.flush()
    A.close()
    B.close()
    print(json.dumps(dict(seconds=round(time.time() - started), net_rows=B.weights.rows)))


if __name__ == '__main__':
    main()
