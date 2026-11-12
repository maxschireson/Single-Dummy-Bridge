"""Card-to-profile distance matrix (G9-B4): how often each profile's generator breaks each card.

Distance = share of covered calls where the card's first fitting rule is not the call made, on the
same random deals for every generator, all four seats bid by it. Residual = the card's families that
the generator breaks on more than 10% of their calls (at least 20 calls).

    python scripts/gen9_profile_distance.py --deals 500 --out reports/gen9-profile-distance-2026-11-12/result.json
"""
import argparse
import json
from pathlib import Path
import random
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bridge_harness import rule_bidder as rb                          # noqa: E402
from bridge_harness.bidding_env import CALLS                          # noqa: E402
from bridge_harness.cards.bidder import CardBidder, bid_table         # noqa: E402
from bridge_harness.cards.match import card_distance                  # noqa: E402

VULS = ('None', 'NS', 'EW', 'Both')
NETS = {'house-gen5': 'models/bidding/gen5-2026-11-10/bidder.keras', 'house-gen6': 'models/bidding/gen6-candidate-2026-11-11/bidder.keras'}
CARDS = ['two-over-one', 'sayc', 'acol', 'precision', 'polish-club', 'rb-standard', 'rb-precision']


def deal_list(n, seed):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        deck = list(range(52))
        rng.shuffle(deck)
        out.append(([sorted(deck[13 * k:13 * k + 13]) for k in range(4)], i % 4, VULS[(i // 4) % 4]))
    return out


def net_bid_deal(path, ds):
    from bridge_harness.system_bidders import BenLstmBidder
    from bridge_harness.system_fit import simulate
    b = BenLstmBidder(path)
    hands = np.array([d[0] for d in ds])
    sim = simulate([b, b], hands, np.array([d[1] for d in ds]), np.array([VULS.index(d[2]) for d in ds]))
    book = {}
    for i, (h, d, v) in enumerate(ds):
        book[(tuple(map(tuple, h)), d, v)] = [CALLS[int(t)] for t in sim['calls'][i] if t >= 0]
    return lambda hands, dealer, vul: book[(tuple(map(tuple, hands)), dealer, vul)]


def generators(ds):
    fallback = rb.RuleSystemBidder(rb.STANDARD, 'same')
    gens = {'rb-standard': rb.RuleSystemBidder(rb.STANDARD, 'standard'), 'rb-precision': rb.RuleSystemBidder(rb.Settings(), 'standard')}
    out = {k: (lambda b: lambda h, d, v: bid_table([b] * 4, h, d, v)[0])(b) for k, b in gens.items()}
    for k, p in NETS.items():
        out[k] = net_bid_deal(p, ds)
    for c in CARDS[:5]:
        out['card:' + c] = (lambda b: lambda h, d, v: bid_table([b] * 4, h, d, v)[0])(CardBidder(c, fallback=fallback))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--deals', type=int, default=500)
    ap.add_argument('--seed', type=int, default=5150)
    ap.add_argument('--out', default=None)
    ap.add_argument('--cards', default=None, help='comma-separated card ids for the columns (default: the seven of G9-B4)')
    ap.add_argument('--generators', default=None, help='comma-separated generator names (default: all)')
    a = ap.parse_args()
    cards = a.cards.split(',') if a.cards else CARDS
    ds = deal_list(a.deals, a.seed)
    gens = generators(ds)
    report = {'deals': a.deals, 'seed': a.seed, 'matrix': {}}
    for g, bid_deal in gens.items():
        if a.generators and g not in a.generators.split(','):
            continue
        row = {}
        for c in cards:
            # card_distance draws its own deals from the seed: the same deals as ds
            r = card_distance(c, bid_deal, deals=a.deals, seed=a.seed)
            row[c] = {'rate': round(r['rate'], 4), 'covered': r['covered'], 'residual': r['residual'],
                      'by_family': {k: v for k, v in r['by_family'].items() if v[0]}}
        report['matrix'][g] = row
        print(g, {c: row[c]['rate'] for c in cards}, flush=True)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
