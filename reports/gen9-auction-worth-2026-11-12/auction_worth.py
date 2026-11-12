"""What the auction reading (the hand-fit scorer) is worth in tricks on p41's stored pools, and how its nats hold
through the play. Readings scored: A = scorer + v4 play reading (the prototype); B = v4 play reading, no auction;
C = scorer only; D = nothing. Costs are double-dummy tricks on the true deal of the card the engine's way would choose."""
import glob, math, sys, json
import numpy as np
sys.path.insert(0, '/home/claude/single-dummy-bridge'); sys.path.insert(0, '/home/claude/bench')
from gen8_reading_bench import load, score, mean_se

POOLS = '/home/claude/pools'
NET = sys.argv[1] if len(sys.argv) > 1 else 'v4'
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 10 ** 9
BANDS = [('tricks 1-2', 1, 2), ('tricks 3-4', 3, 4), ('tricks 5-6', 5, 6), ('tricks 7-9', 7, 9), ('tricks 10-13', 10, 13), ('all', 1, 13)]
out = dict(trick=[], fam=[], regime=[], decl=[], A=[], B=[], C=[], D=[], nats=[], essB=[], drawn=[])
tables = 0
parts = sorted(glob.glob(f'{POOLS}/pools-*-*.npz'))[:LIMIT]
for part in parts:
    rows, tabs, nets = load(part)
    tables += len(tabs)
    with np.load(part.replace('pools-', 'scw-')) as z:
        flat = z['scorer']
    at = 0
    for r in rows:
        L = int(r['layouts'])
        s = flat[at:at + L + 1].astype(np.float64)
        at += L + 1
        fit = np.asarray(r['fit'][NET], np.float64)
        zero = np.zeros_like(fit)
        r2 = dict(r)
        r2['prior'] = (r['prior'].astype(np.float64) - s[:L]).astype(np.float64)
        a = score(r, fit, 1.)
        b = score(r2, fit, 1.)
        c = score(r, zero, 0.)
        d = score(r2, zero, 0.)
        drawn = int(r['regime']) == 0 or int(r['listed']) > L
        if drawn:        # the stored layouts were drawn by the scorer's weights: E_uniform[exp(s)] = 1 / E_pool[exp(-s)]
            m = (-s[:L]).max()
            nats = s[L] + (math.log(np.exp(-s[:L] - m).mean()) + m)
        else:            # every layout is listed
            m = s[:L].max()
            nats = s[L] - (math.log(np.exp(s[:L] - m).mean()) + m)
        out['trick'].append(int(r['trick'])); out['fam'].append(str(r['family'])); out['regime'].append(int(r['regime']))
        out['decl'].append(bool(r['declaring'])); out['drawn'].append(drawn)
        out['A'].append(a[1]); out['B'].append(b[1]); out['C'].append(c[1]); out['D'].append(d[1]); out['nats'].append(nats); out['essB'].append(b[4])
for k in out:
    out[k] = np.array(out[k])
n = len(out['A'])
per_table = n / tables
print(f'net {NET}: {tables} tables, {n} decisions, {per_table:.1f} a table')
print('| Band | Decisions | Scorer nats on the true layout | Auction given the play reading (B - A), tricks a board | Auction alone (D - C) | Play reading given the auction (C - A) | Median effective layouts without the auction |')
print('| --- | ---: | ---: | ---: | ---: | ---: | ---: |')
for name, lo, hi in BANDS + [('declarer deciding', 1, 13), ('defender deciding', 1, 13)]:
    mask = (out['trick'] >= lo) & (out['trick'] <= hi)
    if name == 'declarer deciding':
        mask &= out['decl']
    if name == 'defender deciding':
        mask &= ~out['decl']
    def per_board(v):
        vals = np.where(mask, v, 0.)                      # a band's share of the board: decisions outside it count zero
        m, se = mean_se(vals, out['fam'])
        return f'{m * per_table:+.3f} ± {se * per_table:.3f}'
    nm, nse = mean_se(out['nats'][mask], out['fam'][mask])
    print(f"| {name} | {int(mask.sum()):,} | {nm:+.2f} ± {nse:.2f} | {per_board(out['B'] - out['A'])} | {per_board(out['D'] - out['C'])} | {per_board(out['C'] - out['A'])} | {np.median(out['essB'][mask]):.0f} |")
print('cost a board: A %.3f  B %.3f  C %.3f  D %.3f' % tuple(out[k].mean() * per_table for k in 'ABCD'))
np.savez_compressed('/home/claude/bench/auction_worth_%s.npz' % NET, **{k: v for k, v in out.items() if k != 'fam'}, fam=out['fam'])
