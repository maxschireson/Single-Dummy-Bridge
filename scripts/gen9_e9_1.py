"""E9-1 part 1: what the rule filter recovers on systems the scorer never saw (prediction; no solver).

Registered protocol (team/gen9 experiments/E9-1.md): for each generator, random deals bid with it at
all four seats (or a mixed table); deciders are the opening leader before the lead and declarer at
trick 1. Each decider weights a pool of n layouts of the cards it cannot see, drawn uniformly
(the prior) among those consistent with its view, the true layout included. For a reader R

    G(R) = log(w_R(true) / sum_pool w_R) - log(1 / n)        (nats; 0 = no information)

where log w_R(layout) is the sum over the hidden seats of R's score of that seat's hand.

Readers:
    S        generic hand-fit scorer v0 (trained on Gen 5 bidder auctions)
    S+F      scorer plus the filter from the system's card, eps 0.05, negative inference
    S+F-ni   the same without negative inference
    ceil     the filter alone, eps 0.001, negative inference (the card read as a deterministic generator)
    exact    the generator's own tables as a filter (rule bidder: cards/rb_meanings.py), eps 0.001
    hS+F     extra, labelled: half-weight scorer plus filter

    python scripts/gen9_e9_1.py --deals 2000 --pool 512 --out reports/gen9-e9-1-2026-11-12/result.json
"""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import random
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bridge_harness import rule_bidder as rb                                    # noqa: E402
from bridge_harness.bidding_env import CALL_ID, CALLS                           # noqa: E402
from bridge_harness.cards.context import Context                                # noqa: E402
from bridge_harness.cards.factor import CardFactor, Deviation                   # noqa: E402
from bridge_harness.cards.features import hand_features                         # noqa: E402
from bridge_harness.cards.rb_cards import card_from_settings                    # noqa: E402
from bridge_harness.cards.rb_meanings import RuleBidderMeanings                 # noqa: E402
from bridge_harness.core import auction_contract                                 # noqa: E402
from bridge_harness.gen6_nets import FitScorer, hand_types                       # noqa: E402

VULS = ('None', 'NS', 'EW', 'Both')
SYSTEMS = {
    'standard': rb.STANDARD,
    'precision': rb.Settings(),
    'standard-12-14': replace(rb.STANDARD, nt_lo=12, nt_hi=14),
    'standard-light': replace(rb.STANDARD, open_min=10, open_light=1, weak_lo=4, weak_hi=9),
    'precision-plain': replace(rb.Settings(), stayman=False, transfers=False, jump_overcalls=False, two_diamonds=False),
}
HOUSE = 'models/bidding/gen5-2026-11-10/bidder.keras'
WEIGHTS = ()                     # scorer weights for a grid of w*S + F readers (--weights)


class FixedEps(Deviation):
    def __init__(self, eps):
        super().__init__(eps, 1e9)


class HouseBidder:
    """The Gen 5 LSTM bidder, one deal at a time, through the system_bidders session interface."""

    def __init__(self, path):
        from bridge_harness.system_bidders import BenLstmBidder
        self.b = BenLstmBidder(path)
        self.sessions = {}

    def start(self, hands, dealer, vul):
        self.sessions = {s: self.b.session(np.array([hands[s]]), np.array([s]), np.array([dealer]), np.array([VULS.index(vul)]))
                         for s in range(4)}

    def call(self, hand, seat, dealer, vul, calls):
        legal = np.zeros((1, 40), bool)
        ctx = Context.make([CALLS[t] for t in calls], dealer, seat, VULS[vul] if not isinstance(vul, str) else vul)
        for c in ctx.legal:
            legal[0, CALL_ID[c]] = True
        row = np.full((1, 64), -1, np.int64)
        row[0, :len(calls)] = calls
        return int(self.sessions[seat].act(np.array([0]), row, np.array([len(calls)]), legal)[0])


def bid(bidders, hands, dealer, vul, max_calls=48):
    calls = []
    for b in set(map(id, bidders)):
        pass
    for b in bidders:
        if isinstance(b, HouseBidder):
            b.start(hands, dealer, vul)
            break
    while True:
        seat = (dealer + len(calls)) % 4
        tok = bidders[seat].call(hands[seat], seat, dealer, VULS.index(vul), [CALL_ID[c] for c in calls])
        c = CALLS[tok]
        if c not in Context.make(calls, dealer, seat, vul).legal:
            c = 'PASS'
        calls.append(c)
        n = len(calls)
        if (n >= 4 and calls[-3:] == ['PASS'] * 3 and any(x != 'PASS' for x in calls[:-3])) or (n == 4 and calls == ['PASS'] * 4) or n >= max_calls:
            return calls


def membership(rows):
    m = np.zeros((len(rows), 52), np.int64)
    for i, h in enumerate(rows):
        m[i, list(h)] = 1
    return m


def pool_layouts(rng, hidden_cards, sizes, n):
    """n random splits of hidden_cards into hands of the given sizes."""
    out = []
    cards = list(hidden_cards)
    for _ in range(n):
        rng.shuffle(cards)
        hands, k = [], 0
        for sz in sizes:
            hands.append(sorted(cards[k:k + sz]))
            k += sz
        out.append(hands)
    return out


def gain(lw):
    m = lw.max()
    return float(lw[0] - (m + np.log(np.exp(lw - m).sum())) + np.log(len(lw)))


class Readers:
    def __init__(self, scorer, card, exact):
        self.scorer = scorer
        self.f05 = CardFactor(card, FixedEps(0.05))
        self.f05ni = CardFactor(card, FixedEps(0.05))
        self.f05ni.negative = False
        self.ceil = CardFactor(card, FixedEps(0.001))
        self.exact = CardFactor(exact, FixedEps(0.001)) if exact is not None else None

    def seat(self, length, hon, seat, dealer, vul, calls, exact=True):
        S = self.scorer.type_log_score(length, hon, seat, dealer, vul, calls)
        f = hand_features(length, hon)
        F = self.f05.log_score_features(f, seat, dealer, vul, calls)
        Fni = self.f05ni.log_score_features(f, seat, dealer, vul, calls)
        Fc = self.ceil.log_score_features(f, seat, dealer, vul, calls)
        Fx = self.exact.log_score_features(f, seat, dealer, vul, calls) if self.exact and exact else np.full(len(S), np.nan)
        out = {'S': S, 'S+F': S + F, 'S+F-ni': S + Fni, 'ceil': Fc, 'exact': Fx, 'hS+F': 0.5 * S + F}
        for w in WEIGHTS:
            out[f'{w:g}S+F'] = w * S + F
        return out


def run(name, deals, pool, seed, scorer, exact_deals=500):
    rng = random.Random(seed)
    mixed = name == 'mixed-house-precision'
    g = SYSTEMS['precision' if mixed else name]
    gen = rb.RuleSystemBidder(g, 'standard')
    card = card_from_settings(asdict(g), f'rb-{name}')
    reads = Readers(scorer, card, RuleBidderMeanings(g, 'standard', name))
    house_reads = Readers(scorer, card, None) if mixed else None
    house = HouseBidder(HOUSE) if mixed else None
    rows, skipped = [], 0
    for i in range(deals):
        deck = list(range(52))
        rng.shuffle(deck)
        hands = [sorted(deck[13 * k:13 * k + 13]) for k in range(4)]
        dealer, vul = i % 4, VULS[(i // 4) % 4]
        house_side = i % 2 if mixed else None                      # which side bids with the house bidder
        bidders = [house if mixed and s % 2 == house_side else gen for s in range(4)]
        try:
            calls = bid(bidders, hands, dealer, vul)
        except (ValueError, IndexError):
            skipped += 1
            continue
        contract = auction_contract(dealer, calls)
        if contract is None:
            continue
        decl = contract.declarer
        dummy, leader = (decl + 2) % 4, (decl + 1) % 4
        for role, viewer, hidden in (('leader', leader, [decl, dummy, (leader + 2) % 4]), ('declarer', decl, [leader, (decl + 3) % 4])):
            seen = set(hands[viewer]) | (set(hands[dummy]) if role == 'declarer' else set())
            hidden_cards = [c for c in range(52) if c not in seen]
            layouts = [[hands[s] for s in hidden]] + pool_layouts(rng, hidden_cards, [13] * len(hidden), pool - 1)
            total = None
            for j, s in enumerate(hidden):
                length, hon = hand_types(membership([lay[j] for lay in layouts]))
                rd = house_reads if mixed and s % 2 == house_side else reads
                sc = rd.seat(length, hon, s, dealer, vul, calls, exact=i < exact_deals)
                if mixed and s % 2 == house_side:           # house seats: every reader reads them with the scorer
                    sc = {k: sc['S'] for k in sc}
                total = sc if total is None else {k: total[k] + sc[k] for k in sc}
            row = {k: gain(v) for k, v in total.items() if not np.isnan(v).any()}
            if 'exact' in row:
                row['ceil_on_exact_deals'] = row['ceil']
                row['S_on_exact_deals'] = row['S']
            row.update(deal=i, role=role, contested=sum(1 for c in calls if c not in ('PASS',)) > 0 and len({(dealer + t) % 2 for t, c in enumerate(calls) if c != 'PASS'}) == 2)
            rows.append(row)
    return rows, skipped


def summarize(rows, keys=('S', 'S+F', 'S+F-ni', 'ceil', 'exact', 'hS+F', 'S_on_exact_deals', 'ceil_on_exact_deals')):
    keys = tuple(keys) + tuple(f'{w:g}S+F' for w in WEIGHTS)
    out = {'n': len(rows)}
    for k in keys:
        v = np.array([r[k] for r in rows if k in r])
        if len(v):
            out[k] = [round(float(v.mean()), 3), round(float(v.std(ddof=1) / np.sqrt(len(v))), 3)]
    if 'S' in out and 'ceil' in out:
        gap = out['ceil'][0] - out['S'][0]
        out['recovered_S+F'] = round((out['S+F'][0] - out['S'][0]) / gap, 3) if gap else None
        out['recovered_hS+F'] = round((out['hS+F'][0] - out['S'][0]) / gap, 3) if gap else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--systems', default='standard,precision,standard-12-14,standard-light,precision-plain,mixed-house-precision')
    ap.add_argument('--deals', type=int, default=2000)
    ap.add_argument('--pool', type=int, default=512)
    ap.add_argument('--seed', type=int, default=9901)
    ap.add_argument('--scorer', default='models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz')
    ap.add_argument('--exact-deals', type=int, default=500, help='deals on which the slow exact reader also runs')
    ap.add_argument('--out', default=None)
    ap.add_argument('--weights', default='', help='comma-separated scorer weights w for extra readers w*S + F')
    a = ap.parse_args()
    global WEIGHTS
    WEIGHTS = tuple(float(x) for x in a.weights.split(',') if x)
    scorer = FitScorer(a.scorer)
    report = dict(protocol='E9-1 part 1', deals=a.deals, pool=a.pool, seed=a.seed, scorer=a.scorer, exact_deals=a.exact_deals, systems={})
    for k, name in enumerate(a.systems.split(',')):
        t0 = time.time()
        rows, skipped = run(name, a.deals, a.pool, a.seed + 1000 * k, scorer, a.exact_deals)
        res = {'all': summarize(rows), 'skipped_deals': skipped, 'seconds': round(time.time() - t0)}
        for role in ('leader', 'declarer'):
            res[role] = summarize([r for r in rows if r['role'] == role])
        for flag in (True, False):
            res['contested' if flag else 'uncontested'] = summarize([r for r in rows if r['contested'] == flag])
        report['systems'][name] = res
        print(name, json.dumps(res['all']), res['seconds'], 's', flush=True)
        if a.out:
            Path(a.out).parent.mkdir(parents=True, exist_ok=True)
            Path(a.out).write_text(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
