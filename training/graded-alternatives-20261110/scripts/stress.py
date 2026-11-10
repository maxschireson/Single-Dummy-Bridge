"""How exposed are a bidder's extra contracts to penalty doubles?

usage: stress.py SET[,SET] NAME=path [...]
For every seating where the candidate's side declares a contract that base-vs-base would not have reached,
report the IMPs as bid, the share that make double-dummy, and the IMPs if an opponent had doubled every one
of those contracts (an opponent who knew exactly when the candidate departed from the base).
"""
import os
import sys
from collections import defaultdict

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
import numpy as np

sys.path.insert(0, '/home/claude/gen5r')
sys.path.insert(0, '/home/claude/bid')
import abid  # noqa: E402
import evalnets  # noqa: E402
import diag  # noqa: E402
from bridge_harness.bidding_ppo import Policy  # noqa: E402


def main():
    sets, nets = sys.argv[1].split(','), dict(a.split('=', 1) for a in sys.argv[2:])
    deals = None
    for s in sets:
        d = evalnets.load_set(s)
        deals = d if deals is None else evalnets.join(deals, d)
    n = len(deals)
    base = Policy.load('/home/claude/bid/base.keras')
    _, bb = abid.duplicate(deals, base, base)
    bb_ns = bb.ns_score()[:n]
    c0 = [x[:n] for x in diag.contract(bb)]
    for name, path in nets.items():
        _, auc = abid.duplicate(deals, Policy.load(path), base)
        ns = auc.ns_score()
        cc = diag.contract(auc)
        tot = defaultdict(lambda: np.zeros(5))
        for room, me in ((0, 0), (1, 1)):
            sl = slice(room * n, (room + 1) * n)
            sign = 1 if me == 0 else -1
            lv, st, db, dc, sd = [x[sl] for x in cc]
            lv0, st0, db0, dc0, sd0 = c0
            cat = diag.categorise(lv, st, db, sd, lv0, st0, db0, sd0, me)
            pick = (sd == me) & ((lv != lv0) | (st != st0) | (sd0 != me))
            idx = np.nonzero(pick)[0]
            deal = auc.deal[sl][idx]
            tricks = deals.table[deal, abid.ROW_OF_STRAIN[st[idx]], dc[idx]]
            vul = deals.vulflag[deal, dc[idx]]
            dbl = np.maximum(db[idx], 1)
            s = abid.SCORE[lv[idx] - 1, st[idx], dbl, vul, tricks]
            ns_dbl = np.where(dc[idx] % 2 == 0, s, -s)
            as_bid = abid.imps((ns[sl][idx] - bb_ns[idx]) * sign)
            doubled = abid.imps((ns_dbl - bb_ns[idx]) * sign)
            made = tricks >= lv[idx] + 6
            for j, i in enumerate(idx):
                t = tot[cat[i]]
                t += (1, as_bid[j], doubled[j], made[j], db[i] > 0)
        print(f'\n{name}: {n} deals x 2 seatings; contracts the candidate declares that base-vs-base did not reach')
        total = np.zeros(5)
        for cat, t in sorted(tot.items(), key=lambda kv: -kv[1][0]):
            total += t
            print(f'  {cat:58s} n={int(t[0]):5d}  as bid={t[1]:+7.0f}  if all doubled={t[2]:+7.0f}  make={t[3] / t[0]:5.1%}  already doubled={int(t[4])}')
        print(f'  {"TOTAL":58s} n={int(total[0]):5d}  as bid={total[1]:+7.0f}  if all doubled={total[2]:+7.0f}  make={total[3] / total[0]:5.1%}')


if __name__ == '__main__':
    main()
