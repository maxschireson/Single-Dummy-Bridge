"""Experience: what a player did on finished boards, kept as additive statistics.

Gen 9 design in progress (interface I6 of docs/gen9/architecture.md). Used by no arena bot.

A player's experience is a set of named statistics. Every statistic is a sum over boards, so
collectors on different machines can add theirs in any order and get the same store; a board is
identified by a key and counted once. What a statistic means belongs to whoever defines it (the
bidding and card-play readers); this module only knows four additive shapes and a few
estimators with shrinkage toward a prior.

  count    {'kind': 'count', 'n': {label: number}}
           Labelled tallies. A rate is two labels of one statistic ('agree' and 'deviate'); a
           rate that depends on how many choices there were uses labels such as 'hit/2', 'all/2'.
  hist     {'kind': 'hist', 'lo': first value, 'bins': [numbers]}
           A histogram over consecutive integers starting at `lo` (how far outside a declared
           range a hand was, in points). Histograms with different `lo` or length are aligned.
  moment   {'kind': 'moment', 'grid': [numbers], 'n': number, 'sum': [numbers], 'sumsq': [numbers]}
           Sums of a value observed at every point of a fixed grid on each occasion (the gain in
           the true layout's weight at each play factor). A single value uses a grid of one.
  loglik   {'kind': 'loglik', 'n': number, 'll': {candidate: number}}
           Summed log-likelihood of what the player did under each candidate (profile).
           A candidate missing from one side of a merge is an error: sums over different boards
           cannot be compared.

Documents:

  delta     {'schema': 'experience-delta-v1', 'player': id, 'key': board key, 'stats': {name: statistic}}
            What one finished board adds for one player. The key names the board and table
            (for example '<cohort>/<index>/<table>'), so the same delta can be recognised.
  store     {'schema': 'experience-v1', 'player': id, 'boards': n, 'stats': {...}, 'applied': [keys]}
            The merged statistics. `applied` is the sorted list of delta keys already added.
  snapshot  A store without `applied`, plus 'snapshot': id. This is what a bot is given: it is
            frozen at an epoch boundary and named in every record played under it. A snapshot
            never holds anything about a board still to be played.

Statistic names are namespaced by their owner: 'bid.<family>' and 'profile' (bidding reader),
'card.<signal>' and 'play.<what>' (card-play reader). Hidden hands are used to compute deltas
after a board is over; they are never stored.
"""
from copy import deepcopy
import math

SCHEMA = 'experience-v1'
DELTA_SCHEMA = 'experience-delta-v1'
KINDS = ('count', 'hist', 'moment', 'loglik')


# ---- building statistics ---------------------------------------------------------------------
def count(**labels):
    return dict(kind='count', n={k: float(v) for k, v in labels.items()})


def hist(values, lo=None):
    """A histogram of integer observations."""
    values = [int(v) for v in values]
    if not values:
        return dict(kind='hist', lo=0 if lo is None else int(lo), bins=[])
    lo = min(values) if lo is None else int(lo)
    if min(values) < lo:
        raise ValueError('an observation is below lo')
    bins = [0.] * (max(values) - lo + 1)
    for v in values:
        bins[v - lo] += 1
    return dict(kind='hist', lo=lo, bins=bins)


def moment(grid, values):
    """One occasion: the value observed at every grid point."""
    grid, values = [float(g) for g in grid], [float(v) for v in values]
    if len(grid) != len(values):
        raise ValueError('one value per grid point')
    return dict(kind='moment', grid=grid, n=1., sum=values, sumsq=[v * v for v in values])


def loglik(**candidates):
    """One occasion: the log-likelihood of what was done under each candidate."""
    return dict(kind='loglik', n=1., ll={k: float(v) for k, v in candidates.items()})


# ---- the algebra -----------------------------------------------------------------------------
def check_stat(s):
    if not isinstance(s, dict) or s.get('kind') not in KINDS:
        raise ValueError(f'not a statistic: {s!r}')
    k = s['kind']
    if k == 'count' and not isinstance(s.get('n'), dict):
        raise ValueError('count needs n')
    if k == 'hist' and not (isinstance(s.get('bins'), list) and isinstance(s.get('lo'), int)):
        raise ValueError('hist needs lo and bins')
    if k == 'moment' and not (len(s.get('grid', ())) == len(s.get('sum', ())) == len(s.get('sumsq', ())) and 'n' in s):
        raise ValueError('moment needs grid, n, sum and sumsq of one length')
    if k == 'loglik' and not (isinstance(s.get('ll'), dict) and 'n' in s):
        raise ValueError('loglik needs n and ll')
    return s


def merge_stat(a, b):
    """The sum of two statistics of the same kind. Commutative and associative."""
    check_stat(a), check_stat(b)
    if a['kind'] != b['kind']:
        raise ValueError(f"cannot merge {a['kind']} with {b['kind']}")
    k = a['kind']
    if k == 'count':
        keys = sorted(set(a['n']) | set(b['n']))
        return dict(kind=k, n={x: a['n'].get(x, 0.) + b['n'].get(x, 0.) for x in keys})
    if k == 'hist':
        if not a['bins']:
            return deepcopy(b)
        if not b['bins']:
            return deepcopy(a)
        lo = min(a['lo'], b['lo'])
        hi = max(a['lo'] + len(a['bins']), b['lo'] + len(b['bins']))
        bins = [0.] * (hi - lo)
        for s in (a, b):
            for i, v in enumerate(s['bins']):
                bins[s['lo'] - lo + i] += v
        return dict(kind=k, lo=lo, bins=bins)
    if k == 'moment':
        if list(a['grid']) != list(b['grid']):
            raise ValueError('moments on different grids')
        return dict(kind=k, grid=list(a['grid']), n=a['n'] + b['n'], sum=[x + y for x, y in zip(a['sum'], b['sum'])],
                    sumsq=[x + y for x, y in zip(a['sumsq'], b['sumsq'])])
    if set(a['ll']) != set(b['ll']):
        raise ValueError('log-likelihoods over different candidates')
    return dict(kind=k, n=a['n'] + b['n'], ll={x: a['ll'][x] + b['ll'][x] for x in sorted(a['ll'])})


def merge_stats(a, b):
    """Name by name; a name on one side only is carried over."""
    out = {}
    for name in sorted(set(a) | set(b)):
        out[name] = merge_stat(a[name], b[name]) if name in a and name in b else deepcopy(a.get(name, b.get(name)))
    return out


def empty(player):
    return dict(schema=SCHEMA, player=str(player), boards=0, stats={}, applied=[])


def delta(player, key, stats):
    for s in stats.values():
        check_stat(s)
    return dict(schema=DELTA_SCHEMA, player=str(player), key=str(key), stats=stats)


def add(store, d):
    """The store with one delta added. A delta whose key was already applied changes nothing
    and returns the same store object, so callers can tell."""
    if store.get('schema') != SCHEMA or d.get('schema') != DELTA_SCHEMA:
        raise ValueError('add() takes a store and a delta')
    if store['player'] != d['player']:
        raise ValueError(f"delta for {d['player']!r} offered to the store of {store['player']!r}")
    if 'applied' not in store:
        raise ValueError('a snapshot is frozen: deltas are added to the store')
    if d['key'] in store['applied']:
        return store
    return dict(schema=SCHEMA, player=store['player'], boards=store['boards'] + 1,
                stats=merge_stats(store['stats'], d['stats']), applied=sorted([*store['applied'], d['key']]))


def merge(a, b):
    """Two stores of the same player built from disjoint deltas. Stores that share a delta
    cannot be merged from sums alone: rebuild from the deltas instead."""
    if a['player'] != b['player']:
        raise ValueError('stores of different players')
    if set(a['applied']) & set(b['applied']):
        raise ValueError('the stores share boards: rebuild from the deltas')
    return dict(schema=SCHEMA, player=a['player'], boards=a['boards'] + b['boards'],
                stats=merge_stats(a['stats'], b['stats']), applied=sorted([*a['applied'], *b['applied']]))


def snapshot(store, snapshot_id):
    """What a bot is given: the statistics, frozen, without the list of boards."""
    return dict(schema=SCHEMA, player=store['player'], boards=store['boards'], stats=deepcopy(store['stats']), snapshot=str(snapshot_id))


def check(doc):
    if doc.get('schema') != SCHEMA or not isinstance(doc.get('player'), str) or not isinstance(doc.get('stats'), dict):
        raise ValueError('not an experience-v1 document')
    for s in doc['stats'].values():
        check_stat(s)
    return doc


# ---- estimators: a player with few boards is read as the prior, one with many as themselves ---
def rate(stat, yes, total=None, no=None, prior=(1., 1.)):
    """Posterior mean of a rate under a Beta prior (a, b). Give the label of the successes and
    either the label of the total or the label of the failures. `stat` may be None."""
    a, b = prior
    n = (stat or {}).get('n', {})
    k = n.get(yes, 0.)
    miss = n.get(no, 0.) if no is not None else n.get(total, 0.) - k if total is not None else 0.
    if miss < 0:
        raise ValueError('more successes than occasions')
    return (a + k) / (a + b + k + miss)


def choice_honesty(stat, prior=(1., 1.), options=range(2, 14), steps=200):
    """Honesty h when the prescribed card is played with probability h + (1 - h) / n among n
    choices: the posterior mean on a grid, under a Beta prior on h.

    The default prior has mean 0.5 and the weight of two occasions. E9-4 part 1: assuming more
    honesty than there is costs far more than assuming less (against honesty 0, assuming 0.9
    reads 0.86 nats a decision worse than the right reading; against honesty 1, assuming 0.5
    reads 0.12 worse), and among 0, 0.5, 0.8 and 0.9, 0.5 has the smallest worst case.

    The statistic is a count with labels 'hit/<n>' (prescribed card played) and 'all/<n>'
    (occasions) for each number of choices n. With no data it returns the prior mean."""
    n = (stat or {}).get('n', {})
    data = [(k, n.get(f'hit/{k}', 0.), n.get(f'all/{k}', 0.)) for k in options]
    a, b = prior
    logs = []
    for i in range(steps):
        h = (i + .5) / steps
        lp = (a - 1) * math.log(h) + (b - 1) * math.log(1 - h)
        for k, hit, total in data:
            if total:
                p = h + (1 - h) / k
                lp += hit * math.log(p) + (total - hit) * math.log(max(1 - p, 1e-300))
        logs.append(lp)
    top = max(logs)
    w = [math.exp(x - top) for x in logs]
    return sum((i + .5) / steps * x for i, x in enumerate(w)) / sum(w)


def posterior(stat, prior, temper=1., floor=0.):
    """Probability over candidates from a prior {candidate: p} and summed log-likelihoods.

    With nothing observed (`stat` None or empty) it is the prior. Otherwise every candidate of
    the prior must have been scored: sums over different boards cannot be compared. `temper`
    below 1 slows the update; `floor` is a share spread evenly over all candidates, so none is
    ever ruled out."""
    ll = (stat or {}).get('ll', {})
    if ll and set(prior) - set(ll):
        raise ValueError(f'candidates without a log-likelihood: {sorted(set(prior) - set(ll))}')
    live = {c: p for c, p in prior.items() if p > 0}
    top = max((ll.get(c, 0.) for c in live), default=0.)
    w = {c: p * math.exp(temper * (ll.get(c, 0.) - top)) for c, p in live.items()}
    total = sum(w.values())
    return {c: (1 - floor) * (w.get(c, 0.) / total if total != 1. else w.get(c, 0.)) + floor / len(prior) for c in prior}


def grid_best(stat, prior_mean=None, prior_n=0.):
    """(grid value with the best mean, the means) for a moment statistic, each mean shrunk
    toward `prior_mean` (one value per grid point) as if the prior were `prior_n` occasions.
    Ties go to the grid value nearest 1."""
    grid, n = stat['grid'], stat['n']
    prior_mean = [0.] * len(grid) if prior_mean is None else list(prior_mean)
    if len(prior_mean) != len(grid):
        raise ValueError('one prior mean per grid point')
    means = [(prior_n * m + x) / (prior_n + n) if prior_n + n else m for m, x in zip(prior_mean, stat['sum'])]
    best = max(range(len(grid)), key=lambda i: (means[i], -abs(grid[i] - 1.)))
    return grid[best], means
