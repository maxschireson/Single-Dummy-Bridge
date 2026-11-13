"""First figures for the leakage question, on p41's pools (530 house tables, v4).
A. What a reader as good as our own gains from each thing it reads, by who is reading (tricks a board over no play reading).
B. What it would cost the player who decides to choose evenly among cards within eps tricks of its best (by its own weighted
   solves), double dummy on the true deal, by role; and how often such a choice exists."""
import glob, math, sys
import numpy as np
sys.path.insert(0, '/home/claude/single-dummy-bridge'); sys.path.insert(0, '/home/claude/bench')
from gen8_reading_bench import load, score, mean_se

NET = 'v4'
EPS = (0., 0.02, 0.05, 0.1, 0.2, 0.3)
rows_out = dict(fam=[], decl=[], trick=[], none=[], all=[], opp=[], partner=[], lead=[], n0=[], ncards=[])
for e in EPS:
    rows_out[f'cost{e}'] = []; rows_out[f'n{e}'] = []
tables = 0
for part in sorted(glob.glob('/home/claude/pools/pools-*-*.npz')):
    rows, tabs, nets = load(part)
    tables += len(tabs)
    for r in rows:
        L = int(r['layouts'])
        fit = np.asarray(r['fit'][NET], np.float64)
        zero = np.zeros_like(fit)
        rows_out['fam'].append(str(r['family'])); rows_out['decl'].append(bool(r['declaring'])); rows_out['trick'].append(int(r['trick']))
        rows_out['none'].append(score(r, zero, 0.)[1])
        rows_out['all'].append(score(r, fit, 1.)[1])
        rows_out['lead'].append(score(r, fit, 1., parts=(1., 0., 0.))[1])
        rows_out['partner'].append(score(r, fit, 1., parts=(0., 1., 0.))[1])
        rows_out['opp'].append(score(r, fit, 1., parts=(0., 0., 1.))[1])
        # the decider's own values of its cards, from every stored layout with the reading's weights
        logw = r['prior'].astype(np.float64) + fit[:, :L].sum(0)
        w = np.exp(logw - logw.max()); w /= w.sum()
        u = r['u'].astype(np.float64).reshape(L, -1)
        v = w @ u
        cost = (r['u_true'].max() - r['u_true']).astype(np.float64)
        rows_out['ncards'].append(len(v))
        for e in EPS:
            near = v >= v.max() - e - 1e-9
            rows_out[f'cost{e}'].append(float(cost[near].mean()))
            rows_out[f'n{e}'].append(int(near.sum()))
R = {k: np.array(v) for k, v in rows_out.items()}
n = len(R['none']); per = n / tables; fam = R['fam']
def board(v, mask=None):
    vals = v if mask is None else np.where(mask, v, 0.)
    m, se = mean_se(vals, fam)
    return f'{m * per:+.3f} ± {se * per:.3f}'
print(f'{tables} tables, {n} decisions, {per:.1f} a table')
print('\nA. What the reader gains (tricks a board over no play reading; the auction is read in every row)')
print('| Who is deciding | Every play read | The opponents\' plays alone | Partner\'s plays alone | The opening lead alone |')
print('| --- | ---: | ---: | ---: | ---: |')
for name, mask in (('declarer', R['decl']), ('a defender', ~R['decl']), ('either', np.ones(n, bool))):
    print(f"| {name} | {board(R['none'] - R['all'], mask)} | {board(R['none'] - R['opp'], mask)} | {board(R['none'] - R['partner'], mask)} | {board(R['none'] - R['lead'], mask)} |")
print('\nB. Choosing evenly among the cards within eps tricks of the best (the decider\'s own weighted solves)')
print('| eps | Decisions with more cards to choose from than at eps 0 | Mean cards in the set | Added cost, declarer, tricks a board | Added cost, a defender | Added cost, both |')
print('| ---: | ---: | ---: | ---: | ---: | ---: |')
for e in EPS:
    more = (R[f'n{e}'] > R['n0.0']).mean()
    d = R[f'cost{e}'] - R['cost0.0']
    print(f"| {e} | {more:.1%} | {R[f'n{e}'].mean():.2f} | {board(d, R['decl'])} | {board(d, ~R['decl'])} | {board(d)} |")
print(f"\nexact ties: {np.mean(R['n0.0'] > 1):.1%} of decisions have two or more cards rated exactly equal best; mean legal cards {R['ncards'].mean():.2f}")
np.savez_compressed('/home/claude/bench/leak_first.npz', **{k: v for k, v in R.items()})
