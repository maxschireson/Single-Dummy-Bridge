"""Exact SiD labels for recorded decisions: SPEC.md Part A.

For one episode file (a deal with its recorded tables) this gives, for every decision the dataset builder keeps
(scripts/gen7_build_dataset.py --policy-only) in which the actor holds `cards` or fewer cards, per legal card and
per target (one down, the contract, an overtrick):

  declaring side to play (the position is the declaring side's own view, turned so that it sits North-South)
    guar    the card guarantees the target against every split and every defence
    single  the card wins the true layout's cell (East's exact shape) when that cell is taken alone
    cert    the true layout's cell is in the card's certified set (the cells ONE line starting with it wins)
    floor, ceil   the weight of that set, and of the cells the card wins one at a time
  a defender to play (the position once the card is played, as declarer sees it on the true deal)
    guar    the declaring side then holds a guaranteed line
    cert    the true layout is in the certified set of the declaring side's best-floor card there (only where the
            declaring side plays next, or holds a guaranteed line anyway); floor holds that best floor

The solver is experiments/sure_tricks/cells/cells.cpp through pipeline.Level: shape level, no named card. Weights are
the hand-fit scorer's over every card-fit layout (cells/belief.py: the auction only). Cells are taken heaviest first
to `mass` of the weight; the rest counts as not certified. Answers are per run of touching cards and copied to every
card of the run. A label is -1 where it was not asked: `single` on defender rows, `cert` where a defender plays next,
`single` and `cert` of the other cards when some card guarantees the target outright (unless `full`), and anything a
node cap cut short.

One solver process per Labeller, its tables kept for the whole episode (their entries hold across positions), and a
memory of positions per table entry: a defender's played card leads to the position the declaring side decides
at next, which is then not searched twice.
"""
import json
import sys
import time
from itertools import combinations
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CELLS = ROOT / 'experiments' / 'sure_tricks' / 'cells'
for _p in (str(ROOT), str(CELLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from celllib import SUIT, Solver, cards_of, popcount                      # noqa: E402
from pipeline import Level                                                  # noqa: E402
from bridge_harness.core import Board, Game, card, winner                  # noqa: E402
from bridge_harness.gen6_nets import FitScorer, hand_types                 # noqa: E402

TARGETS = (-1, 0, 1)
SLOTS = 8                       # legal cards a labelled row can have (cards held <= 8)
SKIP = ('replayed_prefix', 'counterfactual_forced', 'forced', 'fixed_opening_lead')     # as the dataset builder
DECLARING, DEFENDER = 0, 1


def mask(cards):
    m = 0
    for c in cards:
        m |= 1 << int(c)
    return m


def unrot(r, side):
    """The real seat of solver seat r (the solver's North-South are the declaring side), as x8_claims."""
    return r if side == 0 else (r + 1) % 4


def rot(seat, side):
    return seat if side == 0 else (seat + 3) % 4


def runs(legal, hand, live):
    """Legal cards grouped into runs of touching cards: no live card outside the hand lies between two of a run.
    `hand` and `live` are masks; live = every card not yet in a finished trick."""
    others = live & ~hand
    out, prev = [], None
    for c in sorted(legal):
        if prev is not None and prev // 13 == c // 13 and not (others & ((1 << c) - 1) & ~((1 << (prev + 1)) - 1)):
            out[-1].append(c)
        else:
            out.append([c])
        prev = c
    return out


class BatchSolver(Solver):
    def ask_many(self, texts):
        """Several questions in one write; the answers in order."""
        for t in texts:
            self._send(t)
        self.proc.stdin.flush()
        return [json.loads(self.proc.stdout.readline()) for _ in texts]


class LabelLevel(Level):
    """A shape-level Level whose single-cell questions go to a chosen list of cells only, in one write."""

    def singles_in(self, cells):
        self.wins = [None] * len(self.cells)
        if not cells:
            return
        kt = ','.join(str(c) for c in self.reps)
        for i, r in zip(cells, self.sv.ask_many(['Q %d %s %d' % (self.pos['need'], kt, i) for i in cells])):
            self.stats['single_sec'] += r['sec']
            self.stats['single_nodes'] += r['nodes']
            self.stats['single_asked'] += 1
            if 'capped' in r:
                self.stats['capped'] += 1
            else:
                self.wins[i] = {int(k): v for k, v in r['cards'].items()}

    def nodes(self):
        return self.stats['single_nodes'] + sum(v['nodes'] for v in self.jstats.values())


class Weights:
    """The hand-fit scorer's weight of every cell of a position (cells/belief.py's quantity, the same arithmetic)."""

    def __init__(self, scorer):
        self.scorer = scorer
        self.combos = {}
        self.seconds = 0.

    def _combos(self, n, k):
        key = (n, k)
        if key not in self.combos:
            self.combos[key] = (np.fromiter((i for c in combinations(range(n), k) for i in c), np.int32).reshape(-1, k)
                                if k else np.zeros((1, 0), np.int32))
        return self.combos[key]

    def cells(self, pos, who):
        """{(eu, 0): weight}, summing to 1. `who` = (East's real seat, West's, the cards each has played (masks),
        dealer, vulnerability, auction)."""
        t0 = time.perf_counter()
        e_real, w_real, e_played, w_played, dealer, vul, auction = who
        pool = cards_of(pos['pool'])
        suit = np.array([c // 13 for c in pool], np.int64)
        forced = np.full(len(pool), -1, np.int8)                # 0 East, 1 West
        for i, c in enumerate(pool):
            if pos['vE'] >> (c // 13) & 1:
                forced[i] = 1
            elif pos['vW'] >> (c // 13) & 1:
                forced[i] = 0
        free = np.flatnonzero(forced < 0)
        need_e = pos['cE'] - int((forced == 0).sum())
        combos = self._combos(len(free), need_e)
        east = np.zeros((len(combos), len(pool)), bool)
        east[:, forced == 0] = True
        if need_e:
            east[np.repeat(np.arange(len(combos)), need_e), free[combos.ravel()]] = True
        logw = np.zeros(len(east))
        for is_east, seat, played in ((True, e_real, e_played), (False, w_real, w_played)):
            member = np.zeros((len(east), 52), np.int8)
            member[:, pool] = east if is_east else ~east
            member[:, cards_of(played)] = 1
            if not (member.sum(axis=1) == 13).all():
                raise ValueError('a hidden hand does not have thirteen cards')
            length, hon = hand_types(member)
            logw += self.scorer.type_log_score(length, hon, seat, dealer, vul, auction)
        w = np.exp(logw - logw.max())
        w /= w.sum()
        key = np.zeros(len(east), np.int64)
        for s in range(4):
            key = key * 16 + east[:, suit == s].sum(axis=1)
        uniq, inv = np.unique(key, return_inverse=True)
        sums = np.bincount(inv.ravel(), weights=w, minlength=len(uniq))
        self.seconds += time.perf_counter() - t0
        return {(((int(k) >> 12) & 15, (int(k) >> 8) & 15, (int(k) >> 4) & 15, int(k) & 15), 0): float(v) for k, v in zip(uniq, sums)}, len(east)


class Labeller:
    def __init__(self, cells_bin, scorer_path, cards=7, mass=.99, maxnodes=20_000_000, defmode='ends', full=False):
        self.flags = ('--def', defmode, '--maxnodes', str(maxnodes))
        self.cells_bin = str(cells_bin)
        self.sv = BatchSolver(self.cells_bin, self.flags)
        self.weights = Weights(FitScorer(scorer_path))
        self.cards, self.mass, self.full = cards, mass, full
        self.memo = {}
        self.count = dict(positions=0, memo_hits=0, capped=0, value_questions=0)

    def close(self):
        self.sv.close()

    def restart(self):
        """A new solver process: after a failure the old one may hold half a question."""
        try:
            self.sv.close()
        except Exception:
            pass
        self.sv = BatchSolver(self.cells_bin, self.flags)
        self.memo = {}

    # ---- one position, from the declaring side's view -----------------------------------------------------------
    def solve(self, pos, east, who, needs, every_card):
        """{need: answer} at a position where the declaring side is to play. An answer is a dict:
        reps; guar {rep: 0/1} (None when capped); single, cert {rep: 0/1/None}; floor, ceil {rep: weight or None};
        best (the best-floor card), best_floor, best_cert; nodes. `every_card`: a certified set for every card (a
        declaring row's labels) and not only for the best one."""
        key = (pos['trump'], pos['leader'], pos['hN'], pos['hS'], pos['pool'], pos['cE'], pos['cW'], pos['vE'], pos['vW'],
               tuple(pos['trick']))
        have = self.memo.setdefault(key, {})
        todo = [n for n in needs if n not in have or (every_card and not have[n]['every_card'])]
        self.count['memo_hits'] += len(needs) - len(todo)
        if todo:
            self.count['positions'] += 1
            lv = LabelLevel(self.sv, dict(pos, need=todo[0]), 0)
            true_i = lv.cell_index(east)
            if true_i is None:
                raise ValueError('the true layout is not among the cells')
            heavy = None
            for need in todo:
                lv.pos['need'] = need
                lv.jstats, lv.sets = {}, {'u': {}, 'b': {}}
                lv.stats.update(single_nodes=0, single_sec=0., single_asked=0, capped=0, seed_failed=0)
                out = lv.outright()
                a = dict(reps=list(lv.reps), every_card=every_card, guar=out, single={}, cert={}, floor={}, ceil={}, best=None,
                         best_floor=0., best_cert=None)
                claim = out is not None and any(out.values())
                if out is not None and claim:
                    a['best'] = next(c for c in lv.reps if out[c])
                    a['best_floor'], a['best_cert'] = 1., 1
                    for c in lv.reps:
                        if out[c]:
                            a['single'][c] = a['cert'][c] = 1
                            a['floor'][c] = a['ceil'][c] = 1.
                if out is not None and (not claim or self.full):
                    if heavy is None:
                        mapping, layouts = self.weights.cells(pos, who)
                        lv.add_weights('b', mapping)
                        w = lv.weights['b']
                        order = sorted(range(len(w)), key=lambda i: -w[i])
                        heavy, total = [], 0.
                        for i in order:
                            if total >= self.mass - 1e-12 or w[i] <= 0:
                                break
                            heavy.append(i)
                            total += w[i]
                        heavy.sort()
                        kept = set(heavy)
                        lv.weights['b'] = [x if i in kept else 0. for i, x in enumerate(w)]     # the rest: not certified
                    lv.singles_in(heavy)
                    if lv.wins[true_i] is not None:
                        true_wins = lv.wins[true_i]
                    else:
                        true_wins = lv.ask([true_i], lv.reps) if true_i not in kept else None
                    ceil = lv.ceiling('b')
                    fl = lv.floors('b', must=lv.reps if every_card else ())
                    for c in lv.reps:
                        if claim and out[c]:
                            continue
                        a['single'][c] = None if true_wins is None else int(true_wins[c])
                        a['ceil'][c] = ceil[c]
                        if c in fl:
                            a['floor'][c], a['cert'][c] = fl[c]['floor'], int(true_i in fl[c]['set'])
                        elif ceil[c] <= 0:
                            a['floor'][c], a['cert'][c] = 0., 0
                        else:
                            a['floor'][c], a['cert'][c] = None, None          # not asked: it could not beat the best floor
                    if not claim:
                        if fl:
                            best = max(sorted(fl, key=lambda c: -ceil[c]), key=lambda c: fl[c]['floor'])
                            a['best'], a['best_floor'], a['best_cert'] = best, fl[best]['floor'], int(true_i in fl[best]['set'])
                        else:
                            a['best_floor'], a['best_cert'] = 0., 0
                a['capped'] = lv.stats['capped']
                if a['capped']:
                    self.count['capped'] += 1
                    a['cert'] = {c: (v if a['guar'] is not None and a['guar'].get(c) else None) for c, v in a['cert'].items()}
                    a['best_cert'] = None if not claim else 1
                a['nodes'] = lv.nodes()
                have[need] = a
        return {n: have[n] for n in needs}

    def value(self, pos):
        """Tricks the declaring side can guarantee at the start of a trick, whoever leads (every cell together)."""
        key = ('V', pos['trump'], pos['leader'], pos['hN'], pos['hS'], pos['pool'], pos['cE'], pos['cW'], pos['vE'], pos['vW'])
        if key not in self.memo:
            lv = Level(self.sv, dict(pos, need=0), 0)
            r = self.sv.value('*')
            self.count['value_questions'] += 1
            self.memo[key] = (None if 'capped' in r else int(r['value']), int(r.get('nodes', 0)))
        return self.memo[key]

    # ---- an episode ----------------------------------------------------------------------------------------------
    def episode(self, d):
        """Labels for every kept decision of an episode (the parsed JSON) with `cards` or fewer cards held."""
        rows = []
        self.sv.reset()
        for ei, e in enumerate(d['unique_tables'].values()):
            if e.get('schema_version') == 'v4-passed-out-v1':
                continue
            board = Board.from_dict(e['board'])
            self.memo = {}
            for ti, table in enumerate(e['tables']):
                game = Game(board)
                actions = table['actions']
                for ai, a in enumerate(actions):
                    x = card(a['card'])
                    actor = game.actor
                    hand = game.hands[actor]
                    if len(hand) <= self.cards:
                        follow = [y for y in hand if y // 13 == game.trick[0][1] // 13] if game.trick else []
                        legal = sorted(follow or hand)
                        est = a.get('estimates')
                        searched = bool(a.get('gen6') and est and len(est) > 1)
                        if (searched or len(legal) > 1) and not any(a.get(k) for k in SKIP):
                            nxt = actions[ai + 1] if ai + 1 < len(actions) else None
                            rows.append(((ei, ti, ai), self.row(board, game, legal, x, nxt)))
                    game.play(x)
        return rows

    def view(self, board, hands, trick, leader, voids):
        """The declaring side's view of a state as a solver position (without `need`), and East's true hand."""
        c = board.contract
        side = c.declarer % 2
        e, w = unrot(1, side), unrot(3, side)
        pos = dict(trump=c.trump, leader=rot(leader, side), hN=mask(hands[unrot(0, side)]), hS=mask(hands[unrot(2, side)]),
                   pool=mask(hands[e]) | mask(hands[w]), cE=len(hands[e]), cW=len(hands[w]), vE=voids[e], vW=voids[w],
                   trick=[y for _, y in trick])
        return pos, mask(hands[e])

    def who(self, board, history, extra=None):
        side = board.contract.declarer % 2
        e, w = unrot(1, side), unrot(3, side)
        played = {e: 0, w: 0}
        for seat, y in (*history, *(() if extra is None else (extra,))):
            if seat in played:
                played[seat] |= 1 << y
        return (e, w, played[e], played[w], board.dealer, board.vulnerability, board.bids)

    @staticmethod
    def show_outs(history):
        voids = {s: 0 for s in range(4)}
        led = None
        for k, (seat, y) in enumerate(history):
            if k % 4 == 0:
                led = y // 13
            elif y // 13 != led:
                voids[seat] |= 1 << led
        return voids

    def row(self, board, game, legal, played, nxt):
        """One decision's labels: dict(role, held, legal, need, guar, single, cert, floor, ceil, ms, nodes); the label
        arrays are [len(legal)][3 targets]."""
        t0 = time.perf_counter()
        c = board.contract
        side = c.declarer % 2
        actor = game.actor
        hand = game.hands[actor]
        won = game.declarer_tricks
        live = mask(y for h in game.hands for y in h) | mask(y for _, y in game.trick)
        groups = runs(legal, mask(hand), live)
        rep_of = {y: g[0] for g in groups for y in g}
        need = [c.level + 6 + j - won for j in TARGETS]
        n = len(legal)
        lab = {k: [[-1] * 3 for _ in range(n)] for k in ('guar', 'single', 'cert')}
        val = {k: [[None] * 3 for _ in range(n)] for k in ('floor', 'ceil')}
        nodes = 0
        voids = self.show_outs(game.history)
        if actor % 2 == side:
            role = DECLARING
            left = len(hand)                                    # tricks still to be won or lost, this one included
            pos, east = self.view(board, game.hands, game.trick, game.leader, voids)
            ask = [nd for nd in need if 0 < nd <= left]
            got = self.solve(pos, east, self.who(board, game.history), sorted(set(ask)), True) if ask else {}
            for t, nd in enumerate(need):
                for i, y in enumerate(legal):
                    if nd <= 0 or nd > left:
                        v = int(nd <= 0)
                        lab['guar'][i][t] = lab['single'][i][t] = lab['cert'][i][t] = v
                        val['floor'][i][t] = val['ceil'][i][t] = float(v)
                        continue
                    a = got[nd]
                    r = rep_of[y]
                    if a['guar'] is None:
                        continue
                    lab['guar'][i][t] = int(a['guar'][r])
                    for k in ('single', 'cert'):
                        if a[k].get(r) is not None:
                            lab[k][i][t] = a[k][r]
                    val['floor'][i][t], val['ceil'][i][t] = a['floor'].get(r), a['ceil'].get(r)
                nodes += got[nd]['nodes'] if nd in got else 0
        else:
            role = DEFENDER
            done = len(game.history) // 4
            for g in groups:
                x = g[0]
                hands = [set(h) for h in game.hands]
                hands[actor].discard(x)
                trick = list(game.trick) + [(actor, x)]
                v2 = dict(voids)
                if game.trick and x // 13 != game.trick[0][1] // 13:
                    v2[actor] |= 1 << (game.trick[0][1] // 13)
                won2, leader2, done2 = won, game.leader, done
                if len(trick) == 4:
                    leader2 = winner(trick, c.trump)
                    won2 += leader2 % 2 == side
                    trick, done2 = [], done + 1
                declaring_next = ((leader2 + len(trick)) % 4) % 2 == side
                need2 = [c.level + 6 + j - won2 for j in TARGETS]
                left2 = 13 - done2
                ask = sorted({nd for nd in need2 if 0 < nd <= left2})
                got, sure = {}, None
                if ask:
                    pos, east = self.view(board, hands, trick, leader2, v2)
                    if declaring_next:
                        # the played card's position is the declaring side's next decision when that is a labelled row
                        every = bool(x == rep_of[played] and nxt is not None and not any(nxt.get(k) for k in SKIP))
                        got = self.solve(pos, east, self.who(board, game.history, (actor, x)), ask, every)
                    else:
                        sure, vn = self.value(pos)
                        nodes += vn
                for t, nd in enumerate(need2):
                    if nd <= 0 or nd > left2:
                        g_, c_, f_ = int(nd <= 0), int(nd <= 0), float(nd <= 0)
                    elif declaring_next:
                        a = got[nd]
                        if a['guar'] is None:
                            continue
                        g_ = int(any(a['guar'].values()))
                        c_, f_ = (1, 1.) if g_ else (a['best_cert'], a['best_floor'])
                    else:
                        if sure is None:
                            continue
                        g_ = int(sure >= nd)
                        c_, f_ = (1, 1.) if g_ else (None, None)     # a guaranteed line is certified whoever leads
                    for i, y in enumerate(legal):
                        if rep_of[y] == x:
                            lab['guar'][i][t] = g_
                            if c_ is not None:
                                lab['cert'][i][t] = c_
                            val['floor'][i][t] = f_
                nodes += sum(a['nodes'] for a in got.values())
        return dict(role=role, held=len(hand), legal=legal, need=need, nodes=nodes, ms=1000. * (time.perf_counter() - t0), **lab, **val)


def pack(rows):
    """Rows of Labeller.episode as the sidecar's arrays."""
    m = len(rows)
    out = dict(key=np.zeros((m, 3), np.int32), role=np.zeros(m, np.int8), held=np.zeros(m, np.int8),
               slots=np.full((m, SLOTS), -1, np.int8), need=np.zeros((m, 3), np.int8),
               guar=np.full((m, SLOTS, 3), -1, np.int8), single=np.full((m, SLOTS, 3), -1, np.int8),
               cert=np.full((m, SLOTS, 3), -1, np.int8), floor=np.full((m, SLOTS, 3), np.nan, np.float16),
               ceil=np.full((m, SLOTS, 3), np.nan, np.float16), ms=np.zeros(m, np.float32), nodes=np.zeros(m, np.int64))
    for i, (key, r) in enumerate(rows):
        n = len(r['legal'])
        out['key'][i], out['role'][i], out['held'][i], out['need'][i] = key, r['role'], r['held'], r['need']
        out['slots'][i, :n] = r['legal']
        out['ms'][i], out['nodes'][i] = r['ms'], r['nodes']
        for k in ('guar', 'single', 'cert'):
            out[k][i, :n] = r[k]
        for k in ('floor', 'ceil'):
            out[k][i, :n] = [[np.nan if v is None else v for v in row] for row in r[k]]
    return out
