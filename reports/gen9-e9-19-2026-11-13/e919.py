"""E9-19, the cheap version (g9, Gen 9): re-score native boards whose two tables' contracts differ by each contract's
double-dummy expectation over layouts consistent with that table's auction, from declarer's view.

For each such table: declarer's hand is fixed; K uniform deals of the other 39 cards are weighted by the hand-fit
scorer's likelihood of the three other seats' calls (as the arena reads a house bot); M layouts are drawn by those
weights; each is solved double dummy at the opening lead (the defenders' best lead), and scored for the contract
as doubled and vulnerable at the table. A board's re-scored result is the candidate's expected IMPs over the pairs of
the two tables' layouts. Boards where both tables reach the same contract (level, strain, doubling and declarer) keep
their result. One JSON line a board; resumable.

usage: python3 e919.py OUT.jsonl BOARDS.json [BOARDS.json ...] --repo REPO --scorer SCORER.npz [--k 2000] [--m 64] [--seed 1919]
"""
import json
import os
import sys
import time

import numpy as np


def arg(flag, default=None, cast=str):
    return cast(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default


REPO = arg('--repo')
sys.path.insert(0, REPO)
from bridge_harness.core import Contract, auction_contract, imps, parse_hand, score, vulnerable    # noqa: E402
from bridge_harness.dds import DDS                                                                  # noqa: E402
from bridge_harness.gen6_nets import FitScorer, hand_types                                          # noqa: E402

SEATS = 'NESW'
IMPS = np.vectorize(imps)


def key_of(c):
    return None if c is None else (c.level, c.strain, c.doubled, c.declarer)


def contract_of(table, dealer):
    calls = table['auction']
    c = auction_contract(dealer, calls)
    if c is None:
        return None
    if c.text() != table['contract'].replace('NT', 'N') and table['contract'] not in ('P', 'PASS', 'Pass'):
        # the table's own record wins on doubling; the auction's on declarer
        c = Contract.parse(table['contract'], SEATS.index(table['declarer']))
    return c


def expected_ns(rng, hands, dealer, vul, table, c, scorer, dds, k, m):
    """NS scores of the table's contract on m layouts drawn from declarer's view, and the effective sample size."""
    if c is None:
        return np.zeros(m), float(k)
    d = c.declarer
    known = list(hands[d])
    rest = np.array([x for x in range(52) if x not in set(known)])
    others = [s for s in range(4) if s != d]
    perm = np.array([rng.permutation(rest) for _ in range(k)])
    logw = np.zeros(k)
    split = {}
    for i, s in enumerate(others):
        cards = perm[:, 13 * i:13 * (i + 1)]
        split[s] = cards
        member = np.zeros((k, 52), np.int8)
        np.put_along_axis(member, cards, 1, axis=1)
        length, hon = hand_types(member)
        logw += scorer.type_log_score(length, hon, s, dealer, vul, table['auction'])
    w = np.exp(logw - logw.max())
    w /= w.sum()
    ess = float(1. / (w ** 2).sum())
    pick = rng.choice(k, size=m, p=w)
    out = np.zeros(m)
    leader = (d + 1) % 4
    for j, i in enumerate(pick):
        layout = [None] * 4
        layout[d] = known
        for s in others:
            layout[s] = [int(x) for x in split[s][i]]
        values, _ = dds.solve(layout, c.trump, leader, [])
        tricks = 13 - max(values.values())
        sc = score(c, tricks, vulnerable(vul, d))
        out[j] = sc if d % 2 == 0 else -sc
    return out, ess


def main():
    out_path, files = sys.argv[1], [a for a in sys.argv[2:] if a.endswith('.json') and not a.startswith('--')]
    k, m, seed = arg('--k', 2000, int), arg('--m', 64, int), arg('--seed', 1919, int)
    scorer = FitScorer(arg('--scorer'))
    dds = DDS()
    done = set()
    if os.path.exists(out_path):
        done = {json.loads(line)['id'] for line in open(out_path)}
    f = open(out_path, 'a')
    for fn in files:
        for b in json.load(open(fn)).values():
            own = (b.get('conditions') or {}).get('own')
            if not own or len(own.get('tables') or []) != 2 or b['id'] in done:
                continue
            cand = b['pair'].split('~')[0]
            board = b['board']
            dealer, vul = SEATS.index(board['dealer']), board['vulnerability']
            hands = [parse_hand(h) for h in board['hands']]
            t1, t2 = own['tables']
            sign = [1 if t['assignments'][0] == cand else -1 for t in (t1, t2)]
            plain = imps(sign[0] * t1['ns_score'] + sign[1] * t2['ns_score'])
            c1, c2 = contract_of(t1, dealer), contract_of(t2, dealer)
            rec = dict(id=b['id'], pair=b['pair'], plain=plain, recorded=own.get('imps'), differ=key_of(c1) != key_of(c2),
                       contracts=[None if c is None else f'{c.text()} {SEATS[c.declarer]}' for c in (c1, c2)])
            if rec['differ']:
                t0 = time.time()
                rng = np.random.default_rng([seed, int(b['id'][-12:], 16) % (1 << 31)])
                s1, e1 = expected_ns(rng, hands, dealer, vul, t1, c1, scorer, dds, k, m)
                s2, e2 = expected_ns(rng, hands, dealer, vul, t2, c2, scorer, dds, k, m)
                grid = IMPS(sign[0] * s1[:, None] + sign[1] * s2[None, :])
                rec.update(rescored=float(grid.mean()), ess=[e1, e2], mean_ns=[float(s1.mean()), float(s2.mean())],
                           seconds=round(time.time() - t0, 2))
            else:
                rec['rescored'] = float(plain)
            f.write(json.dumps(rec) + '\n')
            f.flush()
    dds.close()


if __name__ == '__main__':
    main()
