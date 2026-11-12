"""How many of the cards we play are one of several equal-best cards, how many of those are the same card for the play
(touching cards) and how many are different cards rated equal, and whether the card actually played does better on the
true deal than an even choice among the equal-best. p41's pools (530 house tables), the prototype's reading (v4)."""
import glob, gzip, json, sys, collections
import numpy as np
sys.path.insert(0, '/home/claude/single-dummy-bridge'); sys.path.insert(0, '/home/claude/bench')
from gen8_reading_bench import load, mean_se

SUITS = 'SHDC'; RANKS = '23456789TJQKA'
def num(s): return 13 * SUITS.index(s[0]) + RANKS.index(s[1])
def hand(text): return {13 * i + RANKS.index(ch) for i, part in enumerate(text.split('.')) for ch in part}

rows_out = collections.defaultdict(list)
tables = 0
for part in sorted(glob.glob('/home/claude/pools/pools-*-*.npz')):
    rows, tabs, nets = load(part)
    tables += len(tabs)
    tab = json.load(gzip.open(part.replace('pools-', 'tab-').replace('.npz', '.json.gz'), 'rt'))
    with np.load(part.replace('pools-', 'uns-')) as z:
        actor, controller = z['actor'], z['controller']
    for i, r in enumerate(rows):
        t = tab[int(r['table'])]
        played = [num(c) for c in t['played']]
        ply = int(r['ply'])
        gone = set(played[:ply])
        a = int(actor[i])
        mine = hand(t['board']['hands'][a]) - gone
        legal = [int(c) for c in r['legal']]
        L = int(r['layouts'])
        fit = np.asarray(r['fit']['v4'], np.float64)
        logw = r['prior'].astype(np.float64) + fit[:, :L].sum(0)
        w = np.exp(logw - logw.max()); w /= w.sum()
        v = w @ r['u'].astype(np.float64).reshape(L, -1)
        cost = (r['u_true'].max() - r['u_true']).astype(np.float64)
        best = v >= v.max() - 1e-9
        # touching cards: same suit, and every rank between them is in this hand or already played
        cls = list(range(len(legal)))
        for j in range(1, len(legal)):
            x, y = legal[j - 1], legal[j]
            if x // 13 == y // 13 and all((c in mine) or (c in gone) for c in range(x + 1, y)):
                cls[j] = cls[j - 1]
        best_cls = {cls[j] for j in range(len(legal)) if best[j]}
        rc = played[ply]
        j = legal.index(rc) if rc in legal else -1
        decl = bool(r['declaring'])
        dummy_card = decl and a != int(controller[i])
        rows_out['fam'].append(str(r['family']))
        rows_out['who'].append(0 if (decl and not dummy_card) else 1 if dummy_card else 2)       # declarer's hand, dummy, a defender
        rows_out['legal'].append(len(legal)); rows_out['classes'].append(len(set(cls)))
        rows_out['nbest'].append(int(best.sum())); rows_out['cbest'].append(len(best_cls))
        rows_out['rec_in'].append(j >= 0 and bool(best[j]))
        rows_out['rec_cost'].append(float(cost[j]) if j >= 0 else np.nan)
        rows_out['even_cost'].append(float(cost[best].mean()))
        rows_out['even_class_cost'].append(float(np.mean([cost[[k for k in range(len(legal)) if best[k] and cls[k] == c]].mean() for c in best_cls])))
        rows_out['low_cost'].append(float(cost[np.flatnonzero(best)[0]]))
        rows_out['high_cost'].append(float(cost[np.flatnonzero(best)[-1]]))
        rows_out['bot'].append(str(eval(t['bots'])[int(controller[i])]) if isinstance(t['bots'], str) else str(t['bots'][int(controller[i])]))
R = {k: np.array(v) for k, v in rows_out.items()}
n = len(R['fam']); per = n / tables
print(f'{tables} tables; {n} decisions with a choice after the opening lead ({per:.1f} a table of the 51 cards played after the lead)')
names = {0: "declarer's own hand", 1: 'dummy (declarer choosing)', 2: 'a defender'}
print('\n| Whose card | Decisions a table | Legal cards | Two or more equal best | ... all of them touching (the same card for the play) | ... two or more different cards rated equal | Cards in the equal-best set |')
print('| --- | ---: | ---: | ---: | ---: | ---: | ---: |')
for key in (0, 1, 2, None):
    m = np.ones(n, bool) if key is None else R['who'] == key
    two = m & (R['nbest'] >= 2)
    same = two & (R['cbest'] == 1); diff = two & (R['cbest'] >= 2)
    print(f"| {names.get(key, 'all')} | {m.sum() / tables:.1f} | {R['legal'][m].mean():.2f} | {two.sum() / m.sum():.1%} | {same.sum() / m.sum():.1%} | {diff.sum() / m.sum():.1%} | {R['nbest'][m].mean():.2f} |")
two = R['nbest'] >= 2
print(f"\nOf the 51 cards a table played after the lead: {two.sum() / tables:.1f} ({two.sum() / tables / 51:.0%}) were played with two or more cards rated equal best; "
      f"{(two & (R['cbest'] == 1)).sum() / tables:.1f} with only touching cards equal; {(two & (R['cbest'] >= 2)).sum() / tables:.1f} with different cards equal.")
print(f"The card actually played was among the bench's equal best at {R['rec_in'][two].mean():.1%} of those decisions.")
print('\nOn the true deal, where two or more cards are equal best and the card played was one of them (tricks a board, deal as unit):')
print('| Whose card | Decisions a table | Even among the equal best, minus the card played | Even among the classes, minus the card played | Lowest of them, minus played | Highest, minus played |')
print('| --- | ---: | ---: | ---: | ---: | ---: |')
fam = R['fam']
for key in (0, 1, 2, None):
    m = two & R['rec_in'] & (np.ones(n, bool) if key is None else R['who'] == key)
    def b(x):
        mm, se = mean_se(np.where(m, x, 0.), fam); return f'{mm * per:+.4f} ± {se * per:.4f}'
    rec = np.nan_to_num(R['rec_cost'])
    print(f"| {names.get(key, 'all')} | {m.sum() / tables:.1f} | {b(R['even_cost'] - rec)} | {b(R['even_class_cost'] - rec)} | {b(R['low_cost'] - rec)} | {b(R['high_cost'] - rec)} |")
print('\nby the bot that chose (decisions with two or more equal best and the played card among them): ', {b: int((two & R['rec_in'] & (R['bot'] == b)).sum()) for b in sorted(set(R['bot']))})
for bname in sorted(set(R['bot'])):
    m = two & R['rec_in'] & (R['bot'] == bname) & (R['cbest'] >= 2)
    if m.sum() > 300:
        mm, se = mean_se(np.where(m, R['even_class_cost'] - np.nan_to_num(R['rec_cost']), 0.), fam)
        print(f'  {bname}: different cards rated equal, even among classes minus played: {mm * per:+.4f} ± {se * per:.4f} tricks a board over {m.sum() / tables:.1f} decisions a table')
np.savez_compressed('/home/claude/bench/equal_cards.npz', **R)
