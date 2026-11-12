#!/usr/bin/env python3
"""How fast the shell's profile probabilities move for a guest (G9-D6), using its own functions:
player_model.arrive (prior from the declared card's distances), the 'profile' statistic of
cards.match.profile_evidence summed over boards, and player_model.believed (temper 1, floor 0.02).

A guest partnership bids with one bidder, the other side with another; after each board the statistic
gains that board's log-likelihood of the guest's calls under every candidate. Reported: the believed
probability of each candidate after 0, 1, 2, 5, 10, 20, 50, 100 boards, averaged over --runs orderings.

    python scripts/gen9_arrival_curve.py --guest gen5 --card rb-standard --boards 100 \\
        --out reports/gen9-arrival-curve-2026-11-12/guest-b.json
"""
import argparse
import json
from pathlib import Path
import random
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bridge_harness import player_model as pm                                    # noqa: E402
from bridge_harness.cards.card import load_card                                  # noqa: E402
from bridge_harness.cards.factor import CardFactor, deviation_from               # noqa: E402
from bridge_harness.cards.match import FlatProfile, card_distance, held_systems, profile_evidence  # noqa: E402
import gen9_profile_distance as P                                                # noqa: E402

NETS = {'gen5': 'models/bidding/gen5-2026-11-10/bidder.keras', 'gen6': 'models/bidding/gen6-candidate-2026-11-11/bidder.keras'}
STEPS = (0, 1, 2, 5, 10, 20, 50, 100, 200)


def mixed_auctions(guest, house, ds, guest_side):
    """Auctions of ds with the guest's bidder at guest_side's seats and the house net at the others."""
    from bridge_harness.system_bidders import BenLstmBidder
    from bridge_harness.system_fit import simulate
    from bridge_harness.bidding_env import CALLS
    hands = np.array([d[0] for d in ds])
    dealers = np.array([d[1] for d in ds])
    vuls = np.array([P.VULS.index(d[2]) for d in ds])
    if guest in NETS:
        g = BenLstmBidder(NETS[guest])
        h = BenLstmBidder(NETS[house])
        pair = [g, h] if guest_side == 0 else [h, g]           # simulate([NS bidder, EW bidder], ...)
        sim = simulate(pair, hands, dealers, vuls)
        return [[CALLS[int(t)] for t in sim['calls'][i] if t >= 0] for i in range(len(ds))]
    raise SystemExit('only house-net guests here; rule-bidder guests: scripts/gen9_e9_2.py')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--guest', default='gen5', choices=sorted(NETS))
    ap.add_argument('--house', default='gen6', choices=sorted(NETS))
    ap.add_argument('--card', default='rb-standard', help='the card the guest declares')
    ap.add_argument('--boards', type=int, default=100)
    ap.add_argument('--distance-deals', type=int, default=500)
    ap.add_argument('--runs', type=int, default=20, help='random orderings of the boards')
    ap.add_argument('--seed', type=int, default=9141)
    ap.add_argument('--eps', type=float, default=0.05, help='floor of the held systems\' call models')
    ap.add_argument('--temperature', type=float, default=1.0, help='temperature of the held systems\' call models')
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    systems = held_systems('.', eps=a.eps, temperature=a.temperature)
    card = load_card(a.card)
    # the arrival prior, from the card's distances to every held system (its own cover)
    from bridge_harness.systems import SystemRegistry
    reg = SystemRegistry.load()
    dds = P.deal_list(a.distance_deals, a.seed + 7)
    distances = {}
    for sid in systems:
        bid = P.net_bid_deal(str(Path(__file__).resolve().parents[1] / reg[sid].generator('ben-lstm-keras')['path']), dds)
        distances[sid] = round(card_distance(a.card, bid, deals=a.distance_deals, seed=a.seed + 7)['rate'], 4)
    model = pm.arrive('guest', bidding=json.loads((Path('configs/cards') / f'{a.card}.json').read_text()), distances=distances)
    prior = dict(model.profiles)
    print('distances', distances, 'prior', {k: round(v, 4) for k, v in prior.items()}, flush=True)
    # per-board evidence for the guest's seats
    ds = P.deal_list(a.boards, a.seed)
    auctions = {0: mixed_auctions(a.guest, a.house, ds, 0), 1: mixed_auctions(a.guest, a.house, ds, 1)}
    factor = CardFactor(card, deviation_from(model))
    flat = FlatProfile(list(systems.values()))
    ev = []
    for i, (hands, dealer, vul) in enumerate(ds):
        side = i % 2
        calls = auctions[side][i]
        seats = [s for s in range(4) if s % 2 == side]
        ev.append(profile_evidence(hands, dealer, vul, calls, seats, systems, factor=factor, flat=flat))
        if i % 20 == 19:
            print(f'{i + 1} boards scored', flush=True)
    cands = sorted(prior)
    curves = {c: {k: [] for k in STEPS if k <= a.boards} for c in cands}
    rng = random.Random(a.seed)
    for r in range(a.runs):
        order = list(range(a.boards))
        rng.shuffle(order)
        for k in curves[cands[0]]:
            ll = {c: float(sum(ev[j][c] for j in order[:k])) for c in cands}
            m = pm.PlayerModel('guest', 'guest', prior, model.bidding, None,
                               {'schema': 'experience-v1', 'player': 'guest', 'snapshot': 'sim', 'boards': k,
                                'stats': {pm.PROFILE_STAT: {'kind': 'loglik', 'n': float(k), 'll': ll}}} if k else None)
            post = dict(pm.believed(m).profiles) if k else prior
            for c in cands:
                curves[c][k].append(post.get(c, 0.))
    table = {c: {k: round(float(np.mean(v)), 4) for k, v in curves[c].items()} for c in cands}
    per_board = {c: round(float(np.mean([e[c] for e in ev])), 3) for c in cands}
    report = {'guest': a.guest, 'house': a.house, 'card': a.card, 'eps': a.eps, 'temperature': a.temperature, 'boards': a.boards, 'runs': a.runs, 'seed': a.seed,
              'distances': distances, 'prior': {k: round(v, 4) for k, v in prior.items()}, 'mean_loglik_per_board': per_board,
              'believed_after': table}
    print(json.dumps(report, indent=1))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(report, indent=1) + '\n')


if __name__ == '__main__':
    main()
