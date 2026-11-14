"""E9-1 (preliminary): what the card filter adds to the hand-fit scorer, as the true hand's weight.

For each system, deals are bid with that system at all four seats. For every seat s, an
observer (s's left-hand opponent) weights a pool of random hands for s drawn from the 39 cards
it cannot see, plus s's true hand. The gain of a reader is

    log w(true) - log mean_pool w        (nats; 0 = the reader knows nothing)

for the scorer alone (S), the filter alone (F), both (S+F), and a wrong card's filter (Fw, S+Fw).
This is a prediction measure, not played bridge.

    python scripts/gen9_filter_eval.py --deals 300 --systems sayc,acol,precision,rb:precision
"""
import argparse
import json
from pathlib import Path
import random
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bridge_harness.cards.bidder import CardBidder, bid_table           # noqa: E402
from bridge_harness.cards.factor import CardFactor                       # noqa: E402
from bridge_harness.cards.rb_meanings import RuleBidderMeanings          # noqa: E402
from bridge_harness.gen6_nets import FitScorer, hand_types               # noqa: E402
from bridge_harness import rule_bidder as rb                              # noqa: E402

VULS = ('None', 'NS', 'EW', 'Both')
CARD_FOR = {'house:gen5': 'two-over-one'}       # the card a house pair would declare (house-like, approximate)
HOUSE = {'house:gen5': 'models/bidding/gen5-2026-11-10/bidder.keras'}
WRONG = {'house:gen5': 'precision', 'sayc': 'precision', 'two-over-one': 'precision', 'acol': 'two-over-one', 'precision': 'two-over-one',
         'polish-club': 'two-over-one', 'rb:precision': 'rb:standard', 'rb:standard': 'rb:precision'}


def reader(name):
    name = CARD_FOR.get(name, name)
    if name == 'rb:precision':
        return CardFactor(RuleBidderMeanings(rb.Settings(), 'standard', name))
    if name == 'rb:standard':
        return CardFactor(RuleBidderMeanings(rb.STANDARD, 'standard', name))
    return CardFactor(name)


def bidder(name):
    if name == 'rb:precision':
        return rb.RuleSystemBidder(rb.Settings(), 'standard')
    if name == 'rb:standard':
        return rb.RuleSystemBidder(rb.STANDARD, 'standard')
    return CardBidder(name, fallback=rb.RuleSystemBidder(rb.STANDARD, 'same'))


def membership(hands):
    m = np.zeros((len(hands), 52), np.int64)
    for i, h in enumerate(hands):
        m[i, list(h)] = 1
    return m


def gain(lw):
    rest = lw[1:]
    mx = rest.max()
    return float(lw[0] - (mx + np.log(np.mean(np.exp(rest - mx)))))


def house_auctions(path, deals, seed):
    from bridge_harness.system_bidders import BenLstmBidder
    from bridge_harness.system_fit import simulate
    from bridge_harness.bidding_env import CALLS
    nrng = np.random.default_rng(seed)
    deck = nrng.permuted(np.broadcast_to(np.arange(52), (deals, 52)), axis=1).reshape(deals, 4, 13)
    deck = np.sort(deck, axis=2)
    dealer = np.arange(deals) % 4
    vul = (np.arange(deals) // 4) % 4
    b = BenLstmBidder(path)
    sim = simulate([b, b], deck, dealer, vul)
    out = []
    for i in range(deals):
        calls = [CALLS[int(t)] for t in sim['calls'][i] if t >= 0]
        out.append(([list(map(int, h)) for h in deck[i]], int(dealer[i]), VULS[int(vul[i])], calls))
    return out


def run(system, scorer, deals, pool, seed):
    rng = random.Random(seed)
    house = house_auctions(HOUSE[system], deals, seed) if system in HOUSE else None
    b = None if house else bidder(system)
    true_f, wrong_f = reader(system), reader(WRONG[system])
    rows = []
    for i in range(deals):
        if house:
            hands, dealer, vul, calls = house[i]
        else:
            deck = list(range(52))
            rng.shuffle(deck)
            hands = [sorted(deck[13 * k:13 * k + 13]) for k in range(4)]
            dealer, vul = i % 4, VULS[(i // 4) % 4]
            calls, _ = bid_table([b] * 4, hands, dealer, vul)
        for s in range(4):
            o = (s + 1) % 4
            unseen = [c for c in range(52) if c not in set(hands[o])]
            cands = [hands[s]] + [sorted(rng.sample(unseen, 13)) for _ in range(pool)]
            length, hon = hand_types(membership(cands))
            S = scorer.type_log_score(length, hon, s, dealer, vul, calls)
            F = true_f.type_log_score(length, hon, s, dealer, vul, calls)
            Fw = wrong_f.type_log_score(length, hon, s, dealer, vul, calls)
            covered = len(true_f.seat_terms(calls, dealer, s, vul))
            rows.append(dict(deal=i, seat=s, covered=covered, S=gain(S), F=gain(F), SF=gain(S + F), hSF=gain(0.5 * S + F),
                             Fw=gain(Fw), SFw=gain(S + Fw),
                             auction=' '.join(calls)))
    return rows


def summarize(rows):
    out = {'n': len(rows)}
    for k in ('S', 'F', 'SF', 'hSF', 'Fw', 'SFw'):
        v = np.array([r[k] for r in rows])
        out[k] = [round(float(v.mean()), 3), round(float(v.std(ddof=1) / np.sqrt(len(v))), 3)]
    d = np.array([r['SF'] - r['S'] for r in rows])
    out['SF-S'] = [round(float(d.mean()), 3), round(float(d.std(ddof=1) / np.sqrt(len(d))), 3)]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--systems', default='two-over-one,sayc,acol,precision,polish-club,rb:standard,rb:precision')
    ap.add_argument('--deals', type=int, default=200)
    ap.add_argument('--pool', type=int, default=256)
    ap.add_argument('--seed', type=int, default=9101)
    ap.add_argument('--scorer', default='models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz')
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    scorer = FitScorer(a.scorer)
    report = {'deals': a.deals, 'pool': a.pool, 'seed': a.seed, 'scorer': a.scorer, 'systems': {}}
    for k, system in enumerate(a.systems.split(',')):
        t0 = time.time()
        rows = run(system, scorer, a.deals, a.pool, a.seed + 1000 * k)
        summ = summarize(rows)
        summ['wrong'] = WRONG[system]
        summ['seconds'] = round(time.time() - t0, 1)
        report['systems'][system] = summ
        print(system, json.dumps(summ), flush=True)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
