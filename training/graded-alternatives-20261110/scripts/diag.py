"""Where a bidder's IMPs against the base come from, by kind of change in the final contract.

usage: diag.py SET[,SET] NAME=path [NAME=path ...]
For every deal and seating (candidate NS / candidate EW) the candidate-vs-base auction is compared with
the base-vs-base auction on the same deal. IMPs are from the candidate's side, one seating at a time.
"""
import json
import os
import sys
from collections import defaultdict

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
import numpy as np

sys.path.insert(0, '/home/claude/gen5r')
sys.path.insert(0, '/home/claude/bid')
import abid  # noqa: E402
import evalnets  # noqa: E402
from bridge_harness.bidding_ppo import Policy  # noqa: E402


def contract(auc):
    """level (1-7, 0 passout), strain (CDHSN index), doubled, declarer seat, declaring side (-1 passout)."""
    m = len(auc)
    level, strain = np.zeros(m, np.int64), np.zeros(m, np.int64)
    declarer, side = np.full(m, -1, np.int64), np.full(m, -1, np.int64)
    c = np.nonzero(auc.last >= 0)[0]
    level[c], strain[c] = auc.last[c] // 5 + 1, auc.last[c] % 5
    declarer[c] = auc.first[c, auc.last_seat[c] % 2, strain[c]]
    side[c] = declarer[c] % 2
    return level, strain, auc.doubled.copy(), declarer, side


def klass(level, strain):
    game = ((strain == 4) & (level >= 3)) | ((strain >= 2) & (strain <= 3) & (level >= 4)) | ((strain <= 1) & (level >= 5))
    return np.where(level == 0, 0, np.where(level >= 6, 3, np.where(game, 2, 1)))   # 0 pass, 1 part, 2 game, 3 slam


def categorise(lv, st, db, sd, lv0, st0, db0, sd0, me):
    k, k0 = klass(lv, st), klass(lv0, st0)
    out = np.full(len(lv), 'other', dtype=object)
    mine, mine0 = sd == me, sd0 == me
    theirs, theirs0 = (sd >= 0) & ~mine, (sd0 >= 0) & ~mine0
    both = mine & mine0
    out[both & (k > k0)] = 'we declare: higher class (part->game, game->slam)'
    out[both & (k < k0)] = 'we declare: lower class'
    out[both & (k == k0) & (st != st0)] = 'we declare: same class, other strain'
    out[both & (k == k0) & (st == st0) & (lv != lv0)] = 'we declare: same class and strain, other level'
    out[both & (k == k0) & (st == st0) & (lv == lv0) & (db != db0)] = 'we declare: only the doubling differs'
    out[mine & ~mine0] = 'we declare instead of defending or passing out'
    out[~mine & mine0] = 'we defend or pass out instead of declaring'
    opp = theirs & theirs0
    same = (lv == lv0) & (st == st0)
    out[opp & same & (db > db0)] = 'they declare the same contract: we double'
    out[opp & same & (db < db0)] = 'they declare the same contract: we do not double'
    out[opp & ~same] = 'they declare a different contract'
    out[(sd < 0) & (sd0 < 0)] = 'both passed out'
    return out


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
    c0 = [x[:n] for x in contract(bb)]
    for name, path in nets.items():
        cand = Policy.load(path)
        _, auc = abid.duplicate(deals, cand, base)
        ns = auc.ns_score()
        cc = contract(auc)
        tot = defaultdict(lambda: [0, 0.0, 0, 0])
        changed = 0
        for room, me in ((0, 0), (1, 1)):
            sl = slice(room * n, (room + 1) * n)
            diff = (auc.calls[sl, :48] != bb.calls[:n, :48]).any(axis=1) if auc.calls.shape[1] == bb.calls.shape[1] else None
            if diff is None:
                w = min(auc.calls.shape[1], bb.calls.shape[1])
                diff = (auc.calls[sl, :w] != bb.calls[:n, :w]).any(axis=1) | (auc.n[sl] != bb.n[:n])
            sign = 1 if me == 0 else -1
            gain = abid.imps((ns[sl] - bb_ns) * sign)
            lv, st, db, _, sd = [x[sl] for x in cc]
            lv0, st0, db0, _, sd0 = c0
            cat = categorise(lv, st, db, sd, lv0, st0, db0, sd0, me)
            final_same = (lv == lv0) & (st == st0) & (db == db0) & (cc[3][sl] == c0[3])
            cat[final_same] = 'same final contract and declarer'
            idx = np.nonzero(diff)[0]
            changed += len(idx)
            for i in idx:
                t = tot[cat[i]]
                t[0] += 1; t[1] += float(gain[i]); t[2] += int(gain[i] > 0); t[3] += int(gain[i] < 0)
        print(f'\n{name}: {n} deals x 2 seatings, {changed} auctions differ from base-vs-base')
        rows = sorted(tot.items(), key=lambda kv: -abs(kv[1][1]))
        for cat, (cnt, imps, w, l) in rows:
            print(f'  {cat:58s} n={cnt:5d}  IMPs={imps:+8.0f}  per change={imps / cnt:+6.2f}  W/L={w}/{l}')
        print(f'  {"TOTAL":58s} n={changed:5d}  IMPs={sum(v[1] for v in tot.values()):+8.0f}')
        print(json.dumps({name: {k: v for k, v in tot.items()}}))


if __name__ == '__main__':
    main()
