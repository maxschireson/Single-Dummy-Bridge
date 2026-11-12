"""Gen 9 card meanings and the rule filter (WIP): bridge_harness/cards/."""
import random

import numpy as np
import pytest

from bridge_harness.cards.bidder import CardBidder, bid_table
from bridge_harness.cards.card import builtin_ids, load_card
from bridge_harness.cards.context import Context, legal_calls
from bridge_harness.cards.factor import CardFactor, make_filter
from bridge_harness.cards.features import ANY, C, features_of_hands, hand_features
from bridge_harness.cards.system import CardSystem
from bridge_harness.gen6_nets import hand_types

VULS = ('None', 'NS', 'EW', 'Both')


def deals(n, seed):
    rng = random.Random(seed)
    for i in range(n):
        deck = list(range(52))
        rng.shuffle(deck)
        yield [sorted(deck[13 * k:13 * k + 13]) for k in range(4)], i % 4, VULS[(i // 4) % 4]


def membership(hands):
    m = np.zeros((len(hands), 52), np.int64)
    for i, h in enumerate(hands):
        m[i, list(h)] = 1
    return m


def test_builtin_cards_load_and_compile():
    for cid in builtin_ids():
        card = load_card(cid)
        assert card.unsupported() == []
        rules = CardSystem(card).rules(Context.make([], 0, 0))
        assert rules[-1].pred == ANY


def test_no_card_is_exactly_zero():
    f = make_filter(None)
    length, hon = hand_types(membership([h for d in deals(20, 1) for h in d[0]]))
    assert np.array_equal(f.type_log_score(length, hon, 0, 0, 'None', ['1N', 'PASS']), np.zeros(len(length)))


def test_types_equal_concrete_hands():
    hands = [h for d in deals(2500, 2) for h in d[0]]                 # 10,000 hands
    a = features_of_hands(hands)
    length, hon = hand_types(membership(hands))
    b = hand_features(length, hon)
    for k in a:
        assert np.array_equal(a[k], b[k]), k


def test_own_auctions_fit_every_covered_call():
    """A compiled card's bidder never breaks its own card on covered contexts."""
    for cid in builtin_ids():
        b = CardBidder(cid)
        filt = CardFactor(cid)
        for hands, dealer, vul in deals(150, 3):
            calls, why = bid_table([b] * 4, hands, dealer, vul)
            for s in range(4):
                length, hon = hand_types(membership([hands[s]]))
                lp = filt.type_log_score(length, hon, s, dealer, vul, calls)
                n = len(filt.seat_terms(calls, dealer, s, vul))
                assert lp[0] >= n * np.log(1 - 0.05) - 1e-9, (cid, calls, s)


def test_share_excluded_matches_ranges():
    """1NT 15-17 balanced: about 4.7% of random hands open it in first seat (balanced ~47%, 15-17 ~10%)."""
    hands = [h for d in deals(5000, 4) for h in d[0][:1]]
    f = features_of_hands(hands)
    nt = CardSystem('two-over-one').rules(Context.make([], 0, 0))
    one_nt = next(r for r in nt if r.call == '1N')
    share = one_nt.pred.sat(f).mean()
    expect = ((f['hcp'] >= 15) & (f['hcp'] <= 17) & (f['bal'] == 1)).mean()
    assert share == pytest.approx(expect)
    assert 0.035 < share < 0.06


def test_negative_inference_from_order():
    """A first-seat pass under a 2/1 card makes an opening hand (14 HCP) unlikely."""
    filt = CardFactor('two-over-one')
    f = hand_features(np.array([[4, 3, 3, 3], [4, 3, 3, 3]]), np.array([[1 | 2, 1, 2, 0], [0, 0, 0, 0]]))
    rules = filt.system.rules(Context.make([], 0, 0))
    from bridge_harness.cards.factor import call_log_prob
    lp = call_log_prob(rules, 'PASS', f, 0.05)
    assert lp[0] < np.log(0.06) and lp[1] > np.log(0.95)


def test_legal_calls():
    assert legal_calls([]) [:2] == ['PASS', '1C']
    assert 'X' in legal_calls(['1C'])
    assert 'XX' in legal_calls(['1C', 'X'])
    assert 'X' not in legal_calls(['1C', 'PASS'])


# ---- G9-B2: cards for the rule bidder's settings -------------------------------------------------
from dataclasses import asdict, replace                                       # noqa: E402

from bridge_harness import rule_bidder as rb                                  # noqa: E402
from bridge_harness.cards.rb_cards import card_from_settings, settings_from_card   # noqa: E402

RB_VARIANTS = {
    'standard': rb.STANDARD,
    'precision': rb.Settings(),
    'standard-12-14': replace(rb.STANDARD, nt_lo=12, nt_hi=14),
    'standard-light': replace(rb.STANDARD, open_min=10, open_light=1, weak_lo=4, weak_hi=9),
    'precision-plain': replace(rb.Settings(), stayman=False, transfers=False, jump_overcalls=False, two_diamonds=False),
}


@pytest.mark.parametrize('name', sorted(RB_VARIANTS))
def test_rule_bidder_auctions_never_break_their_card(name):
    """Every covered call in the rule bidder's own auctions is its card's first fitting rule, so every true hand fits."""
    g = RB_VARIANTS[name]
    card = card_from_settings(asdict(g), f'rb-{name}')
    system = CardSystem(card)
    gen = rb.RuleSystemBidder(g, 'standard')
    covered = 0
    for hands, dealer, vul in deals(400, 11):
        try:
            calls, _ = bid_table([gen] * 4, hands, dealer, vul)
        except (ValueError, IndexError):          # rule_bidder.py edge cases, reported to g9
            continue
        for t, call in enumerate(calls):
            seat = (dealer + t) % 4
            rules = system.rules(Context.make(calls[:t], dealer, seat, vul))
            if rules is None:
                continue
            covered += 1
            f = features_of_hands([hands[seat]])
            first = next(r for r in rules if r.pred.dist(f)[0] == 0)
            assert first.call == call, (name, calls[:t], call, first.call, first.label)
    assert covered > 1000


@pytest.mark.parametrize('name', sorted(RB_VARIANTS))
def test_settings_round_trip(name):
    g = RB_VARIANTS[name]
    back, missing = settings_from_card(card_from_settings(asdict(g)))
    assert missing == []
    assert {k: v for k, v in back.items() if getattr(g, k) != v} == {}


def test_written_cards_match_generated():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / 'configs' / 'cards'
    for name, g in (('rb-standard', rb.STANDARD), ('rb-precision', rb.Settings())):
        written = json.loads((root / f'{name}.json').read_text())
        gen = card_from_settings(asdict(g), name)
        assert written['descriptor'] == gen['descriptor'] and written['cover'] == gen['cover']
