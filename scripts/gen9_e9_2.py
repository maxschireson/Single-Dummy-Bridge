"""E9-2: boards needed to identify a system from finished boards (prediction; G9-B4).

Registered protocol (team/gen9 experiments/E9-2.md): for each pair of systems, 1,000 boards bid at
all four seats by the true system; the North-South pair's calls on its actual hands are scored
under every candidate profile (plus `unknown`); boards until the probability of the true system
first stays at or above 0.95, median and 90th percentile over 200 random orderings.

Pairs: the rule bidder's precision and standard settings; the house Gen 6 and Gen 5 bidders; two
compiled 2/1 cards that differ only in the 1NT range (15-17 against 14-16).

Slices: a wrong card declared (prior 0.9 on it); the probability left on `unknown` when the true
system is not among the candidates.

    python scripts/gen9_e9_2.py --boards 1000 --out reports/gen9-e9-2-2026-11-12/result.json
"""
import argparse
import json
from pathlib import Path
import random
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bridge_harness import rule_bidder as rb                                  # noqa: E402
from bridge_harness.bidding_env import CALLS                                  # noqa: E402
from bridge_harness.cards.bidder import CardBidder, bid_table                 # noqa: E402
from bridge_harness.cards.match import (DeterministicProfile, NetProfile, UnknownMixture,  # noqa: E402
                                        board_loglik, boards_to_identify, library)

VULS = ('None', 'NS', 'EW', 'Both')
GEN5 = 'models/bidding/gen5-2026-11-10/bidder.keras'
GEN6 = 'models/bidding/gen6-candidate-2026-11-11/bidder.keras'
NT1416 = {'schema': 'card-descriptor-v0', 'id': 'two-over-one-14-16', 'resp': {'inverted_minors': True},
          'open': {'nt': [{'hcp': [14, 16], 'seats': [1, 2, 3, 4], 'vul': 'any'}]}}


def deals(n, seed):
    rng = random.Random(seed)
    for i in range(n):
        deck = list(range(52))
        rng.shuffle(deck)
        yield [sorted(deck[13 * k:13 * k + 13]) for k in range(4)], i % 4, VULS[(i // 4) % 4]


def net_auctions(path, n, seed):
    from bridge_harness.system_bidders import BenLstmBidder
    from bridge_harness.system_fit import simulate
    b = BenLstmBidder(path)
    out = []
    ds = list(deals(n, seed))
    hands = np.array([d[0] for d in ds])
    dealer = np.array([d[1] for d in ds])
    vul = np.array([VULS.index(d[2]) for d in ds])
    sim = simulate([b, b], hands, dealer, vul)
    for i, (h, d, v) in enumerate(ds):
        out.append((h, d, v, [CALLS[int(t)] for t in sim['calls'][i] if t >= 0]))
    return out


def gen_auctions(bidder, n, seed):
    out = []
    for h, d, v in deals(n, seed):
        try:
            calls, _ = bid_table([bidder] * 4, h, d, v)
        except (ValueError, IndexError):
            continue
        out.append((h, d, v, calls))
    return out


def pair_setup(name, ref):
    fallback = rb.RuleSystemBidder(rb.STANDARD, 'same')
    if name == 'rb-precision-vs-standard':
        cands = [DeterministicProfile('rb-precision', rb.RuleSystemBidder(rb.Settings(), 'standard')),
                 DeterministicProfile('rb-standard', rb.RuleSystemBidder(rb.STANDARD, 'standard'))]
        return cands, lambda n, s: gen_auctions(rb.RuleSystemBidder(rb.Settings(), 'standard'), n, s)
    if name == 'house-gen6-vs-gen5':
        cands = [NetProfile('house-gen6', GEN6), NetProfile('house-gen5', GEN5)]
        return cands, lambda n, s: net_auctions(GEN6, n, s)
    if name == 'card-nt-15-17-vs-14-16':
        cands = [DeterministicProfile('two-over-one', CardBidder('two-over-one', fallback=fallback)),
                 DeterministicProfile('two-over-one-14-16', CardBidder(NT1416, fallback=fallback))]
        return cands, lambda n, s: gen_auctions(CardBidder('two-over-one', fallback=fallback), n, s)
    raise KeyError(name)


def summary(xs):
    reached = [x for x in xs if x is not None]
    if len(reached) < len(xs) / 2:
        return {'median': None, 'p90': None, 'reached': len(reached) / len(xs)}
    arr = np.array([x if x is not None else 10 ** 9 for x in xs])
    p90 = float(np.percentile(arr, 90))
    return {'median': float(np.median(arr)), 'p90': p90 if p90 < 10 ** 9 else None, 'reached': len(reached) / len(xs)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pairs', default='rb-precision-vs-standard,house-gen6-vs-gen5,card-nt-15-17-vs-14-16')
    ap.add_argument('--boards', type=int, default=1000)
    ap.add_argument('--orderings', type=int, default=200)
    ap.add_argument('--seed', type=int, default=7301)
    ap.add_argument('--eps', type=float, default=0.05)
    ap.add_argument('--unknown', default='candidates', choices=('candidates', 'library'))
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    ref = NetProfile('ref-gen5', GEN5)
    report = dict(protocol='E9-2', boards=a.boards, orderings=a.orderings, seed=a.seed,
                  unknown=('per call: 0.8 x the average of the candidates\' distributions + 0.2 uniform over legal calls' if a.unknown == 'candidates'
                           else 'per call: 0.8 x the average over every profile held except the truth (house nets, rule bidder settings, compiled cards) + 0.2 uniform'),
                  eps=a.eps, pairs={})
    for k, name in enumerate(a.pairs.split(',')):
        t0 = time.time()
        cands, make = pair_setup(name, ref)
        for c in cands:
            c.eps = a.eps
        truth = 0
        if a.unknown == 'library':                  # 'some other system': a mixture over every profile we hold
            lib = library('.', exclude={cands[truth].name}, eps=a.eps)
            lib_names = {p.name for p in lib}
            profiles = cands + [UnknownMixture(lib + [c for c in cands if c.name not in lib_names], 0.2)]
            extra = UnknownMixture(lib, 0.2, name='unknown-without-truth')
        else:
            profiles = cands + [UnknownMixture(cands, 0.2)]
            extra = UnknownMixture([c for i, c in enumerate(cands) if i != truth], 0.2, name='unknown-without-truth')
        names = [p.name for p in profiles]
        boards = make(a.boards, a.seed + 100 * k)
        full = [board_loglik(profiles + [extra], h, d, v, calls, (0, 2)) for h, d, v, calls in boards]
        ll = np.array([[b[n] for n in names] for b in full])
        ll_missing = np.array([[b[p.name] for i, p in enumerate(cands) if i != truth] + [b[extra.name]] for b in full])
        uniform = {n: 1 / len(names) for n in names}
        res = {'candidates': names, 'truth': names[truth], 'boards': len(boards)}
        res['to_0.95'] = summary(boards_to_identify(ll, truth, prior=uniform, orderings=a.orderings, seed=k))
        wrong = {n: (0.9 if n == names[1] else 0.1 / (len(names) - 1)) for n in names}
        res['to_0.95_wrong_card_declared'] = summary(boards_to_identify(ll, truth, prior=wrong, orderings=a.orderings, seed=k))
        # the true system missing: how much goes to unknown
        sub = ll_missing
        rng = np.random.default_rng(k)
        share = {}
        for nb in (10, 50, 200, len(boards)):
            vals = []
            for _ in range(a.orderings):
                idx = rng.permutation(len(sub))[:nb]
                s = sub[idx].sum(0)
                s -= s.max()
                p = np.exp(s) / np.exp(s).sum()
                vals.append(p[-1])
            share[str(nb)] = round(float(np.mean(vals)), 3)
        res['unknown_share_when_truth_missing'] = share
        res['mean_loglik_per_board'] = {n: round(float(ll[:, i].mean()), 3) for i, n in enumerate(names)}
        disc = ll[:, 0] - ll[:, 1]
        res['discriminating_boards'] = round(float((np.abs(disc) > 0.5).mean()), 3)
        res['seconds'] = round(time.time() - t0)
        report['pairs'][name] = res
        print(name, json.dumps(res), flush=True)
        if a.out:
            Path(a.out).parent.mkdir(parents=True, exist_ok=True)
            Path(a.out).write_text(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
