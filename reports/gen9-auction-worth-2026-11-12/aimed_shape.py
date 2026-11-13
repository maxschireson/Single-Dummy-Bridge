"""Ceilings on p41's pools, on top of the prototype's reading (v4): what knowing the hidden hands' suit lengths (count) is
worth, what knowing where the honours are is worth, by who decides and when. d_shape = the suits in which a layout gives
hidden seat 0 a different length from the truth; d_hon = honours it misplaces. k large = knowing it (as far as the pool
holds such layouts)."""
import glob, math, sys
import numpy as np
sys.path.insert(0, '/home/claude/single-dummy-bridge'); sys.path.insert(0, '/home/claude/bench')
from gen8_reading_bench import load, score, mean_se

D, tables = [], 0
for part in sorted(glob.glob('/home/claude/pools/pools-*-*.npz')):
    rows, tabs, nets = load(part)
    tables += len(tabs)
    with np.load(part.replace('pools-', 'uns-')) as z:
        cards = z['cards']
    at = 0
    for r in rows:
        L, U = int(r['layouts']), int(r['unseen'])
        c = cards[at:at + U]; at += U
        a, t = r['assign'].reshape(L, U), r['truth'].reshape(1, U)
        suit = c // 13
        shape = np.zeros(L)
        for s in range(4):
            m = suit == s
            if m.any():
                shape += (a[:, m] == 0).sum(1) != (t[:, m] == 0).sum(1)
        hon = (a[:, c % 13 >= 8] != t[:, c % 13 >= 8]).sum(1).astype(np.float64)
        fit = np.asarray(r['fit']['v4'], np.float64)
        logw = r['prior'].astype(np.float64) + fit[:, :L].sum(0)
        D.append(dict(r=r, fit=fit, shape=shape, hon=hon, logw=logw - logw.max(), trick=int(r['trick']), decl=bool(r['declaring']), fam=str(r['family'])))
n = len(D); per = n / tables
fam = np.array([d['fam'] for d in D])
base = np.array([score(d['r'], d['fit'], 1.)[1] for d in D])
trick = np.array([d['trick'] for d in D]); decl = np.array([d['decl'] for d in D])

def gain(d, k, kind):
    w = np.exp(d['logw'])
    return -math.log(max((w * np.exp(-k * d[kind])).sum() / w.sum(), 1e-300))

def calibrate(idx, kind, target):
    lo, hi = 0., 12.
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if np.mean([gain(D[i], mid, kind) for i in idx]) < target else (lo, mid)
    return (lo + hi) / 2

def run(name, mask, kind, target):
    idx = np.flatnonzero(mask)
    k = 12. if target is None else calibrate(idx[::7], kind, target)
    g = float(np.mean([gain(D[i], k, kind) for i in idx]))
    saved = np.zeros(n)
    for i in idx:
        d = D[i]
        r2 = dict(d['r']); r2['prior'] = d['r']['prior'].astype(np.float64) - k * d[kind]
        saved[i] = base[i] - score(r2, d['fit'], 1.)[1]
    m, se = mean_se(saved, fam)
    left = float(np.where(mask, base, 0.).mean() * per)
    what = 'known' if target is None else f'{g:+.2f} nats'
    print(f'| {name} | {"suit lengths" if kind == "shape" else "honours"} | {what} | {g:+.2f} | {m * per:+.4f} ± {se * per:.4f} | {m * per * 3.6:+.3f} | {left:.3f} |', flush=True)

print('| Helped decisions | What is known | How much | Nats a helped decision | Tricks saved a board over the prototype | About, IMPs | The prototype gives up at those decisions |')
print('| --- | --- | --- | ---: | ---: | ---: | ---: |')
early = trick <= 6
for name, mask in (('every decision', np.ones(n, bool)), ('declarer deciding, tricks 1 to 6', decl & early), ('a defender deciding, tricks 1 to 6', ~decl & early),
                   ('declarer deciding, tricks 7 to 13', decl & ~early), ('a defender deciding, tricks 7 to 13', ~decl & ~early)):
    for kind in ('shape', 'hon'):
        for target in (0.3, 0.7, None):
            if target is not None and 'tricks 7' in name:
                continue
            run(name, mask, kind, target)
