"""Write a card for a bidder that has none (disclosure of the house system; G9-D6's guest-b): fit card fields to
the bidder's own auctions by coordinate search, minimising the rate at which the bidder breaks the card on
covered calls, then report the rate on fresh deals.

    python scripts/gen9_fit_card.py --bidder models/bidding/gen5-2026-11-10/bidder.keras --id house-gen5-card \\
        --deals 500 --test 500 --out configs/cards/house-gen5-card.json
"""
import argparse
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bridge_harness.cards.card import unflatten             # noqa: E402
from bridge_harness.cards.match import card_distance        # noqa: E402
import gen9_profile_distance as P                            # noqa: E402

# field -> candidate values (the first is not special: the start card decides where the search begins)
SPACE = {
    'open.min_hcp': [11, 12],
    'open.rule_of_20': [True, False],
    'open.light': [None, {'hcp': 10}, {'hcp': 11}],
    'open.third_seat_min': [9, 10, 11, 12],
    'open.fourth_seat_rule_of_15': [True, False],
    'open.nt': [[{'hcp': [15, 17], 'seats': [1, 2, 3, 4], 'vul': 'any'}], [{'hcp': [14, 16], 'seats': [1, 2, 3, 4], 'vul': 'any'}],
                [{'hcp': [15, 18], 'seats': [1, 2, 3, 4], 'vul': 'any'}], [{'hcp': [14, 17], 'seats': [1, 2, 3, 4], 'vul': 'any'}]],
    'open.nt_five_major': [True, False],
    'open.two_nt': [[20, 21], [20, 22], [19, 21], [21, 22]],
    'open.strong_2c': [{'hcp': 22, 'ltc': 3, 'ltc_hcp': 17, 'call': '2C'}, {'hcp': 22, 'ltc': None, 'call': '2C'},
                       {'hcp': 21, 'ltc': 3, 'ltc_hcp': 17, 'call': '2C'}, {'hcp': 23, 'ltc': 4, 'ltc_hcp': 16, 'call': '2C'}],
    'open.minor': [{'1C_min': 3, '1D_min': 3, 'with_33': '1C', 'with_44': '1D'}, {'1C_min': 3, '1D_min': 3, 'with_33': '1D', 'with_44': '1D'},
                   {'1C_min': 3, '1D_min': 3, 'with_33': '1C', 'with_44': '1C'}, {'1C_min': 2, '1D_min': 3, 'with_33': '1C', 'with_44': '1D'}],
    'open.two': [{'2D': {'type': 'weak', 'hcp': [5, 10], 'len': [6, 6]}, '2H': {'type': 'weak', 'hcp': [5, 10], 'len': [6, 6]}, '2S': {'type': 'weak', 'hcp': [5, 10], 'len': [6, 6]}},
                 {'2D': {'type': 'weak', 'hcp': [5, 11], 'len': [6, 6]}, '2H': {'type': 'weak', 'hcp': [5, 11], 'len': [6, 6]}, '2S': {'type': 'weak', 'hcp': [5, 11], 'len': [6, 6]}},
                 {'2D': {'type': 'weak', 'hcp': [4, 10], 'len': [6, 7]}, '2H': {'type': 'weak', 'hcp': [4, 10], 'len': [5, 6]}, '2S': {'type': 'weak', 'hcp': [4, 10], 'len': [5, 6]}},
                 {'2D': {'type': 'weak', 'hcp': [6, 10], 'len': [6, 6]}, '2H': {'type': 'weak', 'hcp': [6, 10], 'len': [6, 6]}, '2S': {'type': 'weak', 'hcp': [6, 10], 'len': [6, 6]}}],
    'open.weak_quality': [0, 1, 2],
    'open.weak_other_major_max': [3, 4, None],
    'open.three_level': [{'len': 7, 'len_max': 7, 'hcp_min': 0, 'hcp_max': 10}, {'len': 6, 'len_max': 7, 'hcp_min': 0, 'hcp_max': 10},
                         {'len': 7, 'len_max': 8, 'hcp_min': 0, 'hcp_max': 9}],
    'open.three_nt': [{'type': 'gambling'}, None],
    'resp.two_over_one': ['gf', 'standard'],
    'resp.one_nt_to_major': ['forcing', 'semi', 'nf'],
    'resp.single_raise': [[6, 10], [6, 9], [5, 9], [7, 10]],
    'resp.limit_raise': [[10, 12], [10, 11], [11, 12]],
    'resp.limit_raise_len': [3, 4],
    'resp.major_2nt': ['jacoby', 'natural', 'invite'],
    'resp.jacoby_min': [12, 13],
    'resp.splinters': [True, False],
    'resp.inverted_minors': [True, False],
    'resp.minor_2nt': [[11, 12], [13, 15], [10, 12]],
    'comp.overcall_1': [[8, 16], [7, 16], [8, 17], [9, 16]],
    'comp.overcall_2': [[11, 16], [10, 16], [12, 17]],
    'comp.overcall_quality': [{'1': {'top5': 2}, '2': {'top3': 2}, '3': {'top3': 2}}, {'1': {'top5': 1}, '2': {'top5': 2}, '3': {'top5': 2}},
                              {'1': {'top5': 0}, '2': {'top5': 1}, '3': {'top5': 1}}],
    'comp.takeout_double_min': [11, 12, 13],
    'comp.takeout_shape': ['majors', 'all'],
    'comp.nt_overcall': [[15, 18], [15, 17], [16, 18]],
    'comp.michaels': [True, False],
    'comp.unusual_2nt': [True, False],
    'comp.jump_overcall': ['weak', 'intermediate'],
    'comp.negative_double_thru': ['2S', '3S', None],
    'comp.overcall_len': [5, 4],
    'comp.balance': [3, 2, 4],
    'comp.balancing_nt': [[11, 14], [10, 14], [12, 15]],
    'comp.balancing_jumps': [True, False],
    'comp.jump_first': [False, True],
    'comp.michaels_major_min': [8, 6, 10],
    'comp.strong_double_min': [18, 17, 16],
    'comp.weak_jump_hcp': [[5, 10], [4, 9], [6, 11]],
    'resp.major_jump_raise': ['limit', 'weak'],
    'resp.weak_game_raise': [True, False],
    'resp.minor_3nt': [[13, 15], [12, 15], [13, 16]],
    'rebid.one_nt': [None, [12, 14], [11, 14]],
    'rebid.two_nt': [[18, 19], [17, 19], [18, 20]],
    'rebid.reverse_min': [17, 16, 15],
    'rebid.jump_shift_min': [19, 18, 17],
    'slam.blackwood': ['rkc1430', 'rkc3014', 'plain'],
    'slam.gerber': [True, False],
}


def card_with(base, field, value):
    c = copy.deepcopy(base)
    c.setdefault('descriptor', {})[field] = value
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bidder', required=True)
    ap.add_argument('--id', required=True)
    ap.add_argument('--start', default='rb-standard', help='card to start from (its cover is dropped: the fitted card covers every context)')
    ap.add_argument('--deals', type=int, default=500)
    ap.add_argument('--test', type=int, default=500)
    ap.add_argument('--seed', type=int, default=6161)
    ap.add_argument('--rounds', type=int, default=2)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    fit_deals = P.deal_list(a.deals, a.seed)
    test_deals = P.deal_list(a.test, a.seed + 1)
    bid_fit = P.net_bid_deal(a.bidder, fit_deals)
    bid_test = P.net_bid_deal(a.bidder, test_deals)
    start_path = Path(a.start) if Path(a.start).suffix == '.json' else Path(__file__).resolve().parents[1] / 'configs' / 'cards' / f'{a.start}.json'
    start = json.loads(start_path.read_text())
    card = {'schema': 'card-descriptor-v0', 'id': a.id, 'name': f'Card written for the bidder {Path(a.bidder).parent.name}', 'family': 'natural',
            'descriptor': {}}
    nested = unflatten({k: v for k, v in start.items() if k not in ('provenance', 'generator', 'residual', 'cover', 'carding', 'id', 'name',
                                                                   'notes', 'schema', 'family')})
    for sec, fields in nested.items():                   # the start card's own choices, as flat fields
        if isinstance(fields, dict):
            for kk, vv in fields.items():
                card['descriptor'][f'{sec}.{kk}'] = vv

    def rate(c, bid, seed, n):
        """Objective: calls the card gets wrong or is silent on, over the calls in contexts it covers."""
        r = card_distance(c, bid, deals=n, seed=seed)
        return (r['rate'] * r['covered'] + r['silent']) / max(r['covered'] + r['silent'], 1)

    best = rate(card, bid_fit, a.seed, a.deals)
    trace = [('start', a.start, round(best, 4))]
    print('start', round(best, 4), flush=True)
    for r in range(a.rounds):
        improved = False
        for field, values in SPACE.items():
            for v in values:
                c = card_with(card, field, v)
                try:
                    x = rate(c, bid_fit, a.seed, a.deals)
                except Exception as e:                   # a value the card machinery rejects
                    print(f'  {field} = {v}: {type(e).__name__}', flush=True)
                    continue
                if x < best - 1e-9:
                    best, card, improved = x, c, True
                    trace.append((field, v, round(x, 4)))
                    print(f'round {r}: {field} = {v} -> {x:.4f}', flush=True)
        if not improved:
            break
    test = card_distance(card, bid_test, deals=a.test, seed=a.seed + 1)
    start_full = {k: v for k, v in start.items() if k != 'cover'}
    start_test = card_distance(start_full, bid_test, deals=a.test, seed=a.seed + 1)
    start_own = card_distance(start, bid_test, deals=a.test, seed=a.seed + 1)
    card['provenance'] = {'source': f'fitted to the bidder {a.bidder} (its own greedy auctions, all four seats) by scripts/gen9_fit_card.py',
                          'format': 'fitted', 'reader': 'bill (Gen 9), 12 November 2026',
                          'fit': {'deals': a.deals, 'seed': a.seed, 'start_card': a.start, 'rate_fit': round(best, 4), 'steps': trace},
                          'test': {'deals': a.test, 'seed': a.seed + 1, 'objective': round(rate(card, bid_test, a.seed + 1, a.test), 4),
                                   'objective_start_card_full_cover': round(rate(start_full, bid_test, a.seed + 1, a.test), 4),
                                   'rate': round(test['rate'], 4), 'covered': test['covered'], 'silent': test['silent'], 'calls': test['calls'],
                                   'start_card_full_cover': {'rate': round(start_test['rate'], 4), 'covered': start_test['covered'], 'silent': start_test['silent']},
                                   'start_card_own_cover': {'rate': round(start_own['rate'], 4), 'covered': start_own['covered'], 'silent': start_own['silent']},
                                   'residual': test['residual']},
                          'not_placed': ['whatever the bidder does where no card field exists; see test.residual for the families it still breaks']}
    Path(a.out).write_text(json.dumps(card, indent=1) + '\n')
    print(json.dumps(card['provenance']['test']))


if __name__ == '__main__':
    main()
