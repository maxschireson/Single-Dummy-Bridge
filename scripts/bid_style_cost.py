"""What a bidding style costs, double dummy: each deal bid twice by a BEN-format bidder, once plain at all four seats and
once with North-South styled (East-West plain at both tables); each final contract scored by its double-dummy tricks;
the style's cost is North-South's IMPs at the styled table minus the plain one, a board.

Also reports how often the styled seats' calls differ, the contract level, and for the shape dimension whether the
change follows the hand (more bidding with shapely hands for shape > 0, with high cards for shape < 0).

    python scripts/bid_style_cost.py --bidder BUNDLE/artifacts/gen6/bidder.keras --deals 1000 \
        --styles '[{"aggressive": 1, "random": 0.15}]' --near 0.5 1.0 1.5 --out cost.jsonl

All auctions advance in lockstep, one batched bidder call per round.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bridge_harness import bid_style  # noqa: E402
from bridge_harness.bidding_env import CALLS, BidObservation, encode, legal_mask, pack_inputs  # noqa: E402
from bridge_harness.core import auction_contract, imps, score, vulnerable  # noqa: E402

VULS = ('None', 'NS', 'EW', 'Both')


def deals(n, seed):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        cards = list(range(52))
        rng.shuffle(cards)
        hands = tuple(tuple(sorted(cards[13 * s:13 * s + 13])) for s in range(4))
        out.append(dict(hands=hands, dealer=i % 4, vul=VULS[(i // 4 + i) % 4], seed=rng.getrandbits(32)))
    return out


def bid_all(policy, boards, styles, seed):
    """Auctions for every board; styles: {seat: bid style} (unlisted seats plain), or a function of the board index
    returning such a dict. Returns lists of calls and, per styled decision, (board index, seat, plain call, styled call)."""
    rng = random.Random(seed)
    calls = [[] for _ in boards]
    done = [False] * len(boards)
    changes = []
    for _ in range(60):
        live = [i for i in range(len(boards)) if not done[i]]
        if not live:
            break
        obs, masks = [], []
        for i in live:
            b = boards[i]
            seat = (b['dealer'] + len(calls[i])) % 4
            obs.append(encode(BidObservation(b['hands'][seat], seat, b['dealer'], b['vul'], tuple(calls[i]))))
            masks.append(legal_mask(b['dealer'], calls[i]))
        xs, lengths = pack_inputs(obs)
        probs, _ = policy.predict(xs, lengths)
        for k, i in enumerate(live):
            b = boards[i]
            seat = (b['dealer'] + len(calls[i])) % 4
            p = probs[k][lengths[k] - 1] if probs.ndim == 3 else probs[k]
            mask = masks[k]
            plain = int(np.argmax(np.where(mask, p, -np.inf)))
            act = plain
            st = styles(i) if callable(styles) else styles
            if seat in st:
                act = bid_style.choose(p, mask, b['hands'][seat], st[seat], rng.random(), rng.random())
                changes.append((i, seat, plain, act))
            calls[i].append(CALLS[act])
            try:
                auction_contract(b['dealer'], calls[i])
                done[i] = True
            except ValueError:
                pass
    return calls, changes


class DD:
    def __init__(self):
        from bridge_harness.dds import DDS
        self.dds, self.cache = DDS(cache_path=''), {}

    def tricks(self, i, hands, declarer, trump):
        key = (i, declarer, trump)
        if key not in self.cache:
            v, _ = self.dds.solve(hands, trump, (declarer + 1) % 4, [])
            self.cache[key] = 13 - max(v.values())
        return self.cache[key]


def ns_score(dd, i, b, calls):
    c = auction_contract(b['dealer'], calls)
    if c is None:
        return 0, None
    t = dd.tricks(i, b['hands'], c.declarer, c.trump)
    s = score(c, t, vulnerable(b['vul'], c.declarer))
    return (s if c.declarer % 2 == 0 else -s), c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bidder', required=True)
    ap.add_argument('--deals', type=int, default=1000)
    ap.add_argument('--seed', type=int, default=20261114)
    ap.add_argument('--styles', default='[]', help='JSON list of bid styles (without near)')
    ap.add_argument('--personas', type=int, default=0,
                    help='also: a mixed population, North-South on each deal styled by one of this many drawn personas')
    ap.add_argument('--bid-scale', type=float, nargs='+', default=[1.0],
                    help="personas' bidding weights uniform on [-scale, scale] (one population per scale and margin)")
    ap.add_argument('--near-range', nargs='*', default=[],
                    help='personas only: margins drawn per persona, as low:high (e.g. 3:6)')
    ap.add_argument('--near', type=float, nargs='+', default=[1.0])
    ap.add_argument('--out')
    a = ap.parse_args()
    from bridge_harness.bidding_ppo import Policy
    policy = Policy.load(a.bidder)
    boards = deals(a.deals, a.seed)
    dd = DD()
    t0 = time.time()
    base_calls, _ = bid_all(policy, boards, {}, a.seed)
    base = [ns_score(dd, i, b, c) for i, (b, c) in enumerate(zip(boards, base_calls))]
    out = open(a.out, 'a') if a.out else None
    from bridge_harness import persona
    cases = []
    for near in a.near:
        for st in json.loads(a.styles):
            style = bid_style.check(dict(st, near=near))
            cases.append((style, {0: style, 2: style}))
    if a.personas:
        margins = list(a.near) + [tuple(float(x) for x in r.split(':')) for r in a.near_range]
        for near in margins:
            for scale in a.bid_scale:
                prng = random.Random(a.seed + 7)
                pop = [persona.draw(prng, bid_near=near, bid_scale=scale)['bid_style'] for _ in range(a.personas)]
                cases.append(({'population': a.personas, 'near': near, 'scale': scale,
                               'mean_abs': round(float(np.mean([abs(x[k]) for x in pop for k in bid_style.FEATURES])), 3),
                               'mean_random': round(float(np.mean([x['random'] for x in pop])), 3)},
                              lambda i, pop=pop: {0: pop[i % len(pop)], 2: pop[i % len(pop)]}))
    for style, styles in cases:
        calls, changes = bid_all(policy, boards, styles, a.seed + 1)
        res = [ns_score(dd, i, b, c) for i, (b, c) in enumerate(zip(boards, calls))]
        diffs = np.array([imps(r[0] - b0[0]) for r, b0 in zip(res, base)])
        changed = [c for c in changes if c[2] != c[3]]
        more = sum(1 for _, _, p, s in changed if bid_style.action(CALLS[s], []) > bid_style.action(CALLS[p], []))
        # does the change follow the hand? correlation of (styled action - plain action) with the hand's lean
        lean_x, act_y = [], []
        for i, seat, p, s in changes:
            h = boards[i]['hands'][seat]
            lean_x.append((bid_style.distribution_points(h) - bid_style.D_MEAN) / bid_style.D_SD
                          - (bid_style.hcp(h) - bid_style.H_MEAN) / bid_style.H_SD)
            act_y.append(bid_style.action(CALLS[s], []) - bid_style.action(CALLS[p], []))
        corr = float(np.corrcoef(lean_x, act_y)[0, 1]) if len(set(act_y)) > 1 else 0.
        lvl = lambda rs: float(np.mean([r[1].level for r in rs if r[1] is not None]))
        row = dict(style=style, deals=len(boards), imps=round(float(diffs.mean()), 3),
                   se=round(float(diffs.std(ddof=1) / np.sqrt(len(diffs))), 3),
                   boards_changed=round(float(np.mean([r[1] != b0[1] or r[0] != b0[0] for r, b0 in zip(res, base)])), 3),
                   decisions=len(changes), calls_changed=round(len(changed) / max(1, len(changes)), 4),
                   more_action=round(more / max(1, len(changed)), 3),
                   level_plain=round(lvl(base), 3), level_styled=round(lvl(res), 3),
                   shape_minus_points_vs_extra_action=round(corr, 3), seconds=round(time.time() - t0, 1))
        print(json.dumps(row), flush=True)
        if out:
            out.write(json.dumps(row) + '\n')


if __name__ == '__main__':
    main()
