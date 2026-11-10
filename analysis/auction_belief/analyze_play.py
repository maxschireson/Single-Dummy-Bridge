"""Summarise play_info.py output by trick and seat (nats per position)."""
import glob, gzip, json, math, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
files = sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else HERE + '/out/play_*.jsonl*'))
rows = [json.loads(l) for f in files for l in (gzip.open(f, 'rt') if f.endswith('.gz') else open(f))]
se = lambda x: np.std(x, ddof=1) / np.sqrt(len(x)) if len(x) > 1 else float('nan')
print('positions', len(rows), 'deals', len({r['index'] for r in rows}), '; true layout passes the auction test in %.1f%%' % (100 * np.mean([r['true_consistent'] for r in rows])))
print('cards = log count of layouts consistent with cards seen and show-outs; auction = further reduction from the bidder test;')
print('v5 = v5 log-probability of the true layout minus the cards-only log-probability (same units as auction).')
print(f'{"trick":>5} {"view":>9} {"n":>4} {"cards":>6} {"auction":>13} {"v5":>13} {"auction-v5":>13} {"v5>auction":>10} {"median layouts: cards":>21} {"after auction":>13}')
for view in ('all', 'declarer', 'leader', 'third'):
    for T in (2, 4, 6, 8, 10):
        rs = [r for r in rows if r['trick'] == T and (view == 'all' or r['view'] == view) and r['consistent'] > 0]
        if not rs: continue
        cards = np.array([r['log_cards'] for r in rs]); auc = np.array([-math.log(r['consistent'] / r['listed']) for r in rs])
        v5 = np.array([r['logp_v5'] + r['log_cards'] for r in rs]); left = cards - auc
        print(f'{T:>5} {view:>9} {len(rs):>4} {cards.mean():>6.2f} {auc.mean():>6.2f} +-{se(auc):.2f} {v5.mean():>6.2f} +-{se(v5):.2f} {(auc - v5).mean():>6.2f} +-{se(auc - v5):.2f} {100*np.mean(v5 > auc):>9.0f}% {np.median(np.exp(cards)):>21.0f} {np.median(np.exp(left)):>13.0f}')
print('positions with no listed layout passing the auction test (excluded):', sum(r['consistent'] == 0 for r in rows))
