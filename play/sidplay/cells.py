"""The cell game's driver and one declarer-side decision, vendored from experiments/sure_tricks/cells/ at baa062c
(branch research/conditional-claims-20261113): celllib.py (Solver, enumerate_cells and helpers; not Brute) and
pipeline.py (runs_of, honour_runs, Level), unchanged except that the solver's stderr is discarded. See that directory's
DESIGN.md for the game and README.md for its checks.

Cards are ints 13 * suit + rank (2 = 0 ... A = 12). Seats 0..3 = N, E, S, W; North-South declare. Trump 0..3 or 4.
A cell is (eu, pin): eu[s] = East's unnamed cards in suit s, pin = mask of the named cards East holds.
"""

import json
import math
import subprocess
from itertools import combinations, product

SUIT = [0x1FFF << (13 * s) for s in range(4)]


def bits(cards):
    m = 0
    for c in cards:
        m |= 1 << c
    return m


def cards_of(mask):
    out = []
    while mask:
        low = mask & -mask
        out.append(low.bit_length() - 1)
        mask ^= low
    return out


def popcount(x):
    return bin(x).count('1')


class Solver:
    def __init__(self, binary='./cells', flags=()):
        self.proc = subprocess.Popen([binary, *flags], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     text=True, bufsize=1)
        self.ncells = 0

    def _send(self, text):
        self.proc.stdin.write(text + '\n')

    def _ask(self, text):
        self._send(text)
        self.proc.stdin.flush()
        return json.loads(self.proc.stdout.readline())

    def position(self, trump, leader, hN, hS, pool, named=0, trick=()):
        self._send('P %d %d %x %x %x %x %s' % (trump, leader, hN, hS, pool, named, ' '.join(str(c) for c in trick)))
        self.ncells = 0

    def cells(self, cells, weights=None):
        for i, (eu, pin) in enumerate(cells):
            self._send('C %d %d %d %d %x %.12g' % (*eu, pin, 1. if weights is None else weights[i]))
        self.ncells += len(cells)

    def winset(self, need, card, cells='*'):
        ct = cells if cells == '*' else ','.join(str(i) for i in cells)
        return self._ask('W %d %d %s' % (need, card, ct))

    def query(self, need, cells='*', cards='*'):
        ct = cells if cells == '*' else ','.join(str(i) for i in cells)
        kt = cards if cards == '*' else ','.join(str(c) for c in cards)
        r = self._ask('Q %d %s %s' % (need, kt, ct))
        if 'cards' in r:
            r['cards'] = {int(k): v for k, v in r['cards'].items()}
        return r

    def value(self, cells='*'):
        ct = cells if cells == '*' else ','.join(str(i) for i in cells)
        return self._ask('V %s' % ct)

    def reset(self):
        self._send('R')

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def enumerate_cells(pool, cE, cW, voidE=0, voidW=0, named=0):
    """Every cell consistent with the hand sizes and show-outs: list of ((eu0..eu3), pin, layouts in the cell).
    voidE / voidW: suits (bit per suit) East / West is known to hold none of."""
    assert cE + cW == popcount(pool)
    un = [popcount(pool & ~named & SUIT[s]) for s in range(4)]
    nm = cards_of(named & pool)
    out = []
    for r in range(len(nm) + 1):
        for east_named in combinations(nm, r):
            pin = bits(east_named)
            ok = True
            for s in range(4):
                ns = named & pool & SUIT[s]
                if voidE >> s & 1 and pin & SUIT[s]:
                    ok = False
                if voidW >> s & 1 and (ns & ~pin):
                    ok = False
            if not ok:
                continue
            rest = cE - r
            if rest < 0 or cW - (len(nm) - r) < 0:
                continue
            ranges = []
            for s in range(4):
                if voidE >> s & 1:
                    ranges.append([0])
                elif voidW >> s & 1:
                    ranges.append([un[s]])
                else:
                    ranges.append(range(un[s] + 1))
            for eu in product(*ranges):
                if sum(eu) != rest:
                    continue
                w = 1
                for s in range(4):
                    w *= math.comb(un[s], eu[s])
                out.append((eu, pin, w))
    return out


def cell_of(east_hand, pool, named=0):
    """The cell an explicit layout (East's hand as a mask) belongs to."""
    return tuple(popcount(east_hand & ~named & SUIT[s]) for s in range(4)), east_hand & named


def layouts_of(cells, pool, named=0):
    """Every explicit layout (East's hand mask) in the given cells [(eu, pin), ...]."""
    out = set()
    un = [cards_of(pool & ~named & SUIT[s]) for s in range(4)]
    for eu, pin in cells:
        per_suit = [[bits(c) for c in combinations(un[s], eu[s])] for s in range(4)]
        for parts in product(*per_suit):
            out.add(pin | parts[0] | parts[1] | parts[2] | parts[3])
    return frozenset(out)



RANKS = '23456789TJQKA'
SUITS = 'SHDC'


def name(c):
    return SUITS[c // 13] + RANKS[c % 13]


def runs_of(pos):
    """Legal cards of the hand to play, grouped into runs of touching cards (one answer per run)."""
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
    for c in cards_of(legal):
        same = prev is not None and prev // 13 == c // 13 and not (others & ((1 << c) - 1) & ~((1 << (prev + 1)) - 1))
        if same:
            runs[-1].append(c)
        else:
            runs.append([c])
        prev = c
    return runs


def honour_runs(pos):
    """Runs of unseen touching cards that have a North-South card of the suit below them, as dicts (card = the run's top
    card). Single cards first, those with North-South cards on both sides before those above every North-South card,
    then by rank."""
    ns = pos['hN'] | pos['hS']
    out = []
    for s in range(4):
        mine, theirs = cards_of(ns & SUIT[s]), cards_of(pos['pool'] & SUIT[s])
        if not mine or not theirs:
            continue
        runs = []
        for c in theirs:
            if runs and not any(runs[-1][-1] < x < c for x in mine):
                runs[-1].append(c)
            else:
                runs.append([c])
        for run in runs:
            below = sum(1 for x in mine if x < run[0])
            above = sum(1 for x in mine if x > run[-1])
            if below:
                out.append(dict(card=run[-1], length=len(run), below=below, above=above))
    out.sort(key=lambda r: (r['length'], -(r['above'] > 0), -(r['card'] % 13)))
    return out


class Level:
    def __init__(self, sv, pos, named=0, parent=None, cap_cells=500):
        self.sv, self.pos, self.named, self.parent = sv, pos, named, parent
        cells = enumerate_cells(pos['pool'], pos['cE'], pos['cW'], pos['vE'], pos['vW'], named)
        cells.sort(key=lambda t: -t[2])
        total = sum(w for _, _, w in cells)
        self.dropped = {'u': 0.}
        if len(cells) > cap_cells:
            self.dropped['u'] = sum(w for _, _, w in cells[cap_cells:]) / total
            cells = cells[:cap_cells]
        self.cells = cells
        self.weights = {'u': [w / total for _, _, w in cells]}
        self.index = {(eu, pin): i for i, (eu, pin, _) in enumerate(cells)}
        self.runs = runs_of(pos)
        self.reps = [r[0] for r in self.runs]
        self.stats = dict(cells=len(cells), single_sec=0., single_nodes=0, single_asked=0, capped=0, seed_failed=0)
        self.jstats = {}
        self.sets = {'u': {}}
        if parent is not None:
            assert parent.named & ~named == 0
            extra = named & ~parent.named
            self.up = []
            for eu, pin, _ in cells:
                ceu = tuple(eu[s] + popcount(pin & extra & SUIT[s]) for s in range(4))
                self.up.append(parent.index.get((ceu, pin & parent.named)))
        self.sv.position(pos['trump'], pos['leader'], pos['hN'], pos['hS'], pos['pool'], named, pos['trick'])
        self.sv.cells([(eu, pin) for eu, pin, _ in cells])

    def add_weights(self, key, mapping):
        """Another weighting of the cells: mapping {(eu, pin): weight}, summing to 1 over all cells of the level."""
        self.weights[key] = [mapping.get((eu, pin), 0.) for eu, pin, _ in self.cells]
        self.dropped[key] = max(0., 1. - sum(self.weights[key]))
        self.sets[key] = {}

    def ask(self, cells, cards='*', into=None):
        r = self.sv.query(self.pos['need'], cells, cards)
        st = self.stats if into is None else self.jstats.setdefault(into, dict(sec=0., nodes=0, queries=0))
        if into is None:
            st['single_sec'] += r['sec']
            st['single_nodes'] += r['nodes']
        else:
            st['sec'] += r['sec']
            st['nodes'] += r['nodes']
            st['queries'] += 1
        if 'capped' in r:
            self.stats['capped'] += 1
            return None
        return r['cards']

    def outright(self):
        """Per card: does it guarantee the target in every cell (one question)."""
        got = self.ask('*', into='outright')
        return None if got is None else {c: got[c] for c in self.reps}

    def singles(self):
        """wins[i][c] for every cell i and card c. Answers a parent settles are not asked again."""
        self.wins = []
        for i in range(len(self.cells)):
            have = {}
            if self.parent is not None and self.up[i] is not None and self.parent.wins[self.up[i]] is not None:
                have = {c: 1 for c, v in self.parent.wins[self.up[i]].items() if v}
            todo = [c for c in self.reps if c not in have]
            if todo:
                got = self.ask([i], todo)
                self.stats['single_asked'] += 1
                if got is None:
                    self.wins.append(None)
                    continue
                have.update({c: got[c] for c in todo})
            self.wins.append(have)

    def ceiling(self, key):
        w = self.weights[key]
        return {c: sum(w[i] for i, g in enumerate(self.wins) if g is not None and g[c]) for c in self.reps}

    def seed_for(self, c, key):
        """The sub-cells of the parent's set for card c: won by the parent's line, so a valid starting set."""
        if self.parent is None or key not in self.parent.sets or c not in self.parent.sets[key]:
            return []
        keep = set(self.parent.sets[key][c])
        return [i for i in range(len(self.cells)) if self.up[i] in keep]

    def joint(self, c, key):
        """(floor, set, questions, whole): the cells card c wins alone, asked as one set (whole = that held); otherwise
        grown from the seed, heaviest cell first. Cells of no weight are left out."""
        w = self.weights[key]
        R = [i for i, g in enumerate(self.wins) if g is not None and g[c] and w[i] > 0]
        if not R:
            self.sets[key][c] = []
            return 0., [], 0, True
        if len(R) == 1:
            self.sets[key][c] = R
            return w[R[0]], R, 0, True
        q = 1
        got = self.ask(R, [c], into=key)
        if got is not None and got[c]:
            self.sets[key][c] = R
            return sum(w[i] for i in R), R, q, True
        inR = set(R)
        S = [i for i in self.seed_for(c, key) if i in inR]
        if len(S) > 1:
            got = self.ask(S, [c], into=key)            # must hold; counted when it does not
            q += 1
            if got is None or not got[c]:
                self.stats['seed_failed'] += 1
                S = []
        inS = set(S)
        for i in sorted(R, key=lambda i: -w[i]):
            if i in inS:
                continue
            if not S:
                S, inS = [i], {i}
                continue
            got = self.ask(S + [i], [c], into=key)
            q += 1
            if got is not None and got[c]:
                S.append(i)
                inS.add(i)
        self.sets[key][c] = S
        return sum(w[i] for i in S), S, q, False

    def floors(self, key, must=()):
        """Joint floors in falling order of ceiling; a card whose ceiling cannot beat the best floor found is skipped
        unless listed in `must` or holding a set at the parent level (so that sets can be refined)."""
        ceil = self.ceiling(key)
        out, best = {}, 0.
        keep = set(must) | (set(self.parent.sets.get(key, {})) if self.parent is not None else set())
        for c in sorted(self.reps, key=lambda c: -ceil[c]):
            if ceil[c] <= 0 or (ceil[c] <= best + 1e-12 and c not in keep):
                continue
            f, S, q, whole = self.joint(c, key)
            out[c] = dict(floor=f, set=S, questions=q, whole=whole)
            best = max(best, f)
        return out

    def cell_index(self, east_hand):
        """The cell an explicit layout belongs to (East's hand as a mask), or None when it was dropped."""
        eu = tuple(popcount(east_hand & ~self.named & SUIT[s]) for s in range(4))
        return self.index.get((eu, east_hand & self.named))
