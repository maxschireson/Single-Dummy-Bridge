"""What information of a given kind, at given decisions, is worth in tricks on p41's pools, on top of the prototype's reading (v4).

Each stored layout's weight is multiplied by exp(-k x d), d = the cards of a kind (small: 2 to 9; honours: T to A) that the layout
gives to the wrong hidden seat. k is set so that the true layout gains a target number of nats on average over the helped
decisions. This is the bench's proxy for a reader that knows something about lengths (count signals) or about honours
(attitude signals, the auction) at those decisions."""
import glob, math, sys
import numpy as np
sys.path.insert(0, '/home/claude/single-dummy-bridge'); sys.path.insert(0, '/home/claude/bench')
from gen8_reading_bench import load, score, mean_se

NET = 'v4'
D = []          # per decision: dict(r, small, hon, logw, trick, decl, fam)
tables = 0
for part in sorted(glob.glob('/home/claude/pools/pools-*-*.npz')):
    rows, tabs, nets = load(part)
    tables += len(tabs)
    with np.load(part.replace('pools-', 'uns-')) as z:
        cards = z['cards']
    at = 0
    for r in rows:
        L, U = int(r['layouts']), int(r['unseen'])
        c = cards[at:at + U]; at += U
        wrong = (r['assign'].reshape(L, U) != r['truth'].reshape(1, U))
        small = (c % 13 < 8)
        fit = np.asarray(r['fit'][NET], np.float64)
        logw = r['prior'].astype(np.float64) + fit[:, :L].sum(0)
        D.append(dict(r=r, fit=fit, small=wrong[:, small].sum(1).astype(np.float64), hon=wrong[:, ~small].sum(1).astype(np.float64),
                      logw=logw - logw.max(), trick=int(r['trick']), decl=bool(r['declaring']), fam=str(r['family'])))
n = len(D)
per = n / tables
fam = np.array([d['fam'] for d in D])
base = np.array([score(d['r'], d['fit'], 1.)[1] for d in D])

def gain(d, k, kind):
    w = np.exp(d['logw'])
    return -math.log((w * np.exp(-k * d[kind])).sum() / w.sum())

def calibrate(idx, kind, target):
    lo, hi = 0., 8.
    for _ in range(40):
        mid = (lo + hi) / 2
        g = np.mean([gain(D[i], mid, kind) for i in idx])
        lo, hi = (mid, hi) if g < target else (lo, mid)
    return (lo + hi) / 2

def run(name, mask, kind, target):
    idx = np.flatnonzero(mask)
    k = calibrate(idx[::7], kind, target)                       # a seventh of the helped decisions is enough to set k
    g = float(np.mean([gain(D[i], k, kind) for i in idx]))
    saved = np.zeros(n)
    for i in idx:
        d = D[i]
        r2 = dict(d['r']); r2['prior'] = d['r']['prior'].astype(np.float64) - k * d[kind]
        saved[i] = base[i] - score(r2, d['fit'], 1.)[1]
    m, se = mean_se(saved, fam)
    print(f'| {name} | {kind} | {len(idx):,} ({len(idx) / tables:.1f} a board) | {k:.3f} | {g:+.2f} | {m * per:+.4f} ± {se * per:.4f} | {m * per * 3.6:+.3f} |', flush=True)

trick = np.array([d['trick'] for d in D]); decl = np.array([d['decl'] for d in D])
print(f'{tables} tables, {n} decisions; prototype cost {base.mean() * per:.3f} tricks a board')
print('| Helped decisions | Kind of card | Decisions | k | Nats a helped decision | Tricks saved a board over the prototype | About, IMPs a board |')
print('| --- | --- | ---: | ---: | ---: | ---: | ---: |')
early = trick <= 6
for name, mask in (('every decision', np.ones(n, bool)), ('declarer deciding, tricks 1 to 6', decl & early), ('a defender deciding, tricks 1 to 6', ~decl & early)):
    for kind in ('small', 'hon'):
        for target in ((0.3, 0.7, 1.5) if name == 'every decision' else (0.3, 0.7)):
            run(name, mask, kind, target)
