"""Conditional claims for the declaring side, for X9 (Gen 9 task G9-A11; design `experiments/sure_tricks/cells/DESIGN.md`
section 6 on `research/conditional-claims-20261113` at `baa062c`; plan `docs/gen9/sid-integration.md` on `feature/gen9`).
Work in progress; nothing here is adopted or deployed.

A **cell** is East's number of cards in each suit, with the declaring side turned to North-South as `x8_claims` turns
it; every unseen card stays pooled (no named cards: the shape level). A card's **certified set** is a set of cells in
all of which ONE line starting with that card takes the tricks the contract still needs against every defence; its
**floor** is the set's weight. The solver is `cells` (`experiments/sure_tricks/cells/cells.cpp` at `baa062c`, built as
`g++ -O2 -march=native -std=c++17 -o cells cells.cpp`, found by `CELLS_BIN`).

The cells and their weights come from the decision's own layouts and weights (for X9: Gen 9's reading), heaviest first
until `mass` of the weight is covered (DESIGN step 1). Each cell is asked alone for every candidate (the ceiling, step
2); then, for candidates in falling order of ceiling, the joint step (3): the card's winning cells asked as one
question, else a set grown heaviest cell first, keeping a cell when the enlarged set still holds. Every set kept has
been asked as one question, so a set is valid even when the time allowance ends the step early.

Brought over from `experiments/sure_tricks/cells/celllib.py` and `pipeline.py` (same commit): the solver protocol and
the joint step. Changed: cells come from the layouts (not every cell consistent with the hand sizes), a wall-clock
allowance per decision, and the commitment question (DESIGN section 6, "Commitment").
"""
import json
import os
import subprocess
import time

from .x8_claims import rot, show_outs

SUIT = [0x1FFF << (13 * s) for s in range(4)]


def bits(cards):
    m = 0
    for c in cards:
        m |= 1 << int(c)
    return m


def popcount(x):
    return bin(x).count('1')


class Cells:
    """One `cells` process (its tables stay valid across positions)."""

    def __init__(self, binary=None, maxnodes=2_000_000):
        self.binary = binary or os.environ.get('CELLS_BIN', 'cells')
        if not (os.path.isfile(self.binary) and os.access(self.binary, os.X_OK)):
            raise RuntimeError(f'The cells solver was not found at {self.binary!r}: build experiments/sure_tricks/cells/cells.cpp '
                               '(research/conditional-claims-20261113) and set CELLS_BIN')
        self.flags = ('--def', 'ends', '--maxnodes', str(int(maxnodes)))
        self.proc = None
        self.queries = 0
        self.seconds = 0.

    def _start(self):
        if self.proc is None or self.proc.poll() is not None:
            self.proc = subprocess.Popen([self.binary, *self.flags], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def _send(self, text):
        self._start()
        self.proc.stdin.write(text + '\n')

    def _ask(self, text):
        self._send(text)
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            self.close()
            raise RuntimeError('the cells solver stopped')
        return json.loads(line)

    def position(self, pos, cells):
        self._send('P %d %d %x %x %x %x %s' % (pos['trump'], pos['leader'], pos['hN'], pos['hS'], pos['pool'], 0,
                                               ' '.join(str(c) for c in pos['trick'])))
        for eu in cells:
            self._send('C %d %d %d %d %x %.12g' % (*eu, 0, 1.))

    def query(self, need, cells, cards):
        """{card: 1/0} for one question over the cells (indices into the last position's cells), or None if capped."""
        started = time.perf_counter()
        r = self._ask('Q %d %s %s' % (need, ','.join(str(int(c)) for c in cards), ','.join(str(int(i)) for i in cells)))
        self.queries += 1
        self.seconds += time.perf_counter() - started
        if 'capped' in r:
            return None
        return {int(k): v for k, v in r['cards'].items()}

    def close(self):
        if self.proc is not None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()
            self.proc = None


def position(o):
    """The declaring side to play, turned so it sits North-South: (pos, east seat, side) or None when the contract is
    already made or lost. pos as the cells pipeline has it: trump, leader, hN, hS, pool, cE, cW, vE, vW, trick, need."""
    c = o.contract
    need = c.level + 6 - o.declarer_tricks
    left = len(o.known_hands[o.actor])
    if need <= 0 or need > left:
        return None
    side = c.declarer % 2
    played = {x for _, x in o.history}
    mine = set(o.known_hands[c.declarer]) | set(o.known_hands[c.dummy])
    pool = [x for x in range(52) if x not in played and x not in mine]
    voids = show_outs(o)
    hands = {rot(c.declarer, side): o.known_hands[c.declarer], rot(c.dummy, side): o.known_hands[c.dummy]}
    real = {rot(s, side): s for s in range(4)}
    count = {rot(s, side): 13 - sum(1 for seat, _ in o.history if seat == s) for s in range(4) if s % 2 != side}
    void = {rot(s, side): voids[s] for s in range(4) if s % 2 != side}
    pos = dict(trump=c.trump, leader=rot(o.leader, side), hN=bits(hands[0]), hS=bits(hands[2]), pool=bits(pool), cE=count[1],
               cW=count[3], vE=void[1], vW=void[3], trick=[int(x) for _, x in o.trick], need=need)
    return pos, real[1], side


def cell_of(east_mask):
    return tuple(popcount(east_mask & SUIT[s]) for s in range(4))


def runs_of(pos):
    """Legal cards of the hand to play in runs of touching cards (as pipeline.runs_of)."""
    seat = (pos['leader'] + len(pos['trick'])) & 3
    h = pos['hN'] if seat == 0 else pos['hS']
    legal = h
    if pos['trick']:
        f = h & SUIT[pos['trick'][0] // 13]
        if f:
            legal = f
    live = pos['hN'] | pos['hS'] | pos['pool']
    for c in pos['trick']:
        live |= 1 << c
    others = live & ~h
    runs, prev = [], None
    c = legal
    order = []
    while c:
        low = c & -c
        order.append(low.bit_length() - 1)
        c ^= low
    for x in order:
        if prev is not None and prev // 13 == x // 13 and not (others & ((1 << x) - 1) & ~((1 << (prev + 1)) - 1)):
            runs[-1].append(x)
        else:
            runs.append([x])
        prev = x
    return runs


def decide(solver, o, worlds, w, reps, mass=.99, allowance=2., min_weight=0.):
    """Certified sets and floors for candidate cards `reps` (real card ids) at a declaring-side decision.

    Returns None when the position is settled, else a dict: cells [eu], weight [w] (normalized over all layouts),
    covered (weight of the cells asked), layout_cell [index or -1 per layout], floor {rep: weight}, ceiling {rep},
    set {rep: [cell indices]}, queries, seconds, complete (False when the allowance ended the work)."""
    got = position(o)
    if got is None:
        return None
    pos, east, _ = got
    started = time.perf_counter()
    total = float(sum(w))
    weight = {}
    for k, world in enumerate(worlds):
        eu = cell_of(bits(world[east]))
        weight[eu] = weight.get(eu, 0.) + float(w[k]) / total
    order = sorted(weight, key=lambda eu: -weight[eu])
    cells, acc = [], 0.
    for eu in order:
        if acc >= mass - 1e-12:
            break
        cells.append(eu)
        acc += weight[eu]
    index = {eu: i for i, eu in enumerate(cells)}
    layout_cell = [index.get(cell_of(bits(world[east])), -1) for world in worlds]
    runs = runs_of(pos)
    rep_of = {}
    for run in runs:
        for x in run:
            rep_of[x] = run[0]
    asked = sorted({rep_of[x] for x in reps if x in rep_of})
    out = dict(cells=[list(eu) for eu in cells], weight=[round(weight[eu], 6) for eu in cells], covered=round(acc, 6),
               layout_cell=layout_cell, floor={}, ceiling={}, set={}, queries=0, seconds=0., complete=True, need=pos['need'])
    if not asked or not cells:
        return out
    solver.position(pos, cells)
    queries0 = solver.queries

    def late():
        return time.perf_counter() - started > allowance

    wins = []
    for i in range(len(cells)):
        if late():
            out['complete'] = False
            break
        wins.append(solver.query(pos['need'], [i], asked))
    ceiling = {}
    for c in asked:
        ceiling[c] = sum(weight[cells[i]] for i, g in enumerate(wins) if g is not None and g.get(c))
    best = 0.
    for c in sorted(asked, key=lambda c: -ceiling[c]):
        if ceiling[c] <= max(best, min_weight) + 1e-12 or late():
            continue
        R = [i for i, g in enumerate(wins) if g is not None and g.get(c)]
        S = []
        if len(R) == 1:
            S = R
        elif R:
            g = solver.query(pos['need'], R, [c])
            if g is not None and g.get(c):
                S = R
            else:
                for i in sorted(R, key=lambda i: -weight[cells[i]]):
                    if late():
                        out['complete'] = False
                        break
                    if not S:
                        S = [i]
                        continue
                    g = solver.query(pos['need'], S + [i], [c])
                    if g is not None and g.get(c):
                        S.append(i)
        f = sum(weight[cells[i]] for i in S)
        out['set'][c], out['floor'][c] = S, round(f, 6)
        best = max(best, f)
    out['ceiling'] = {c: round(v, 6) for c, v in ceiling.items()}
    out['rep_of'] = {int(x): int(rep_of[x]) for x in reps if x in rep_of}
    out['queries'] = solver.queries - queries0
    out['seconds'] = round(time.perf_counter() - started, 4)
    return out


def live_cells(commit, o):
    """The committed set's cells as they stand now: East's counts less East's cards played since, dropping cells the
    play has ruled out. None when this is not the same deal's declaring side after the commitment."""
    hist = tuple((int(a), int(b)) for a, b in o.history)
    if hist[:len(commit['history'])] != commit['history'] or o.controller % 2 != commit['side']:
        return None
    east = commit['east']
    played = [0, 0, 0, 0]
    for seat, x in hist[len(commit['history']):]:
        if seat == east:
            played[x // 13] += 1
    got = position(o)
    if got is None:
        return None
    pos = got[0]
    pool = [popcount(pos['pool'] & SUIT[s]) for s in range(4)]
    out = []
    for eu in commit['cells']:
        now = tuple(eu[s] - played[s] for s in range(4))
        if any(n < 0 or n > pool[s] for s, n in enumerate(now)) or sum(now) != pos['cE']:
            continue
        if any(pos['vE'] >> s & 1 and now[s] for s in range(4)) or any(pos['vW'] >> s & 1 and now[s] != pool[s] for s in range(4)):
            continue
        out.append(now)
    return sorted(set(out))


def keeping(solver, o, cells):
    """The legal cards that keep the line over `cells` (one question), or None when no answer came."""
    got = position(o)
    if got is None or not cells:
        return None
    pos = got[0]
    runs = runs_of(pos)
    rep_of = {x: run[0] for run in runs for x in run}
    reps = sorted(set(rep_of.values()))
    solver.position(pos, cells)
    ans = solver.query(pos['need'], list(range(len(cells))), reps)
    if ans is None:
        return None
    return {x for x in o.legal if ans.get(rep_of.get(int(x), -1))}
