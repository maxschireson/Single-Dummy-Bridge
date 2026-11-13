"""Conditional guarantees at one declarer-side decision: outright, by shape, and with named honours.

A position is a dict: trump, leader, hN, hS, pool (ints), cE, cW, vE, vW, trick (list), need.

A Level is one choice of named cards: its cells, and for each card (one per run of touching cards) whether the card
wins each cell taken alone (`wins`, one search per cell; independent of any weights). A level can carry several
weightings of its cells ('u' = uniform over card-fit layouts is always there; add others with add_weights). For a
weighting and a card:
  ceiling   the weight of the cells in which the card wins when the cell is taken alone (fused over cells)
  floor     the weight of a set of cells that ONE line starting with the card wins; the set is grown from a seed
            (the refinement of a coarser level's set, when there is one) by adding cells heaviest first and keeping
            a cell when the enlarged set still holds as one yes/no question
A level built on a parent (same position, fewer named cards) inherits: a card that wins a parent cell alone wins
each of its sub-cells alone, and the sub-cells of a parent's set are won by the same line.
"""
from celllib import SUIT, cards_of, enumerate_cells, popcount

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
