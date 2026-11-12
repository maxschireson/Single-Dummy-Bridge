"""Gen 9 card meanings and the rule filter (WIP): bridge_harness/cards/."""
import json
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


# ---- G9-B4: distance and detection ---------------------------------------------------------------
from pathlib import Path as _Path                                                     # noqa: E402

from bridge_harness.cards.match import (DeterministicProfile, UnknownMixture, board_loglik,   # noqa: E402
                                        boards_to_identify, card_distance, experience_delta)

GEN5 = _Path(__file__).resolve().parents[1] / 'models/bidding/gen5-2026-11-10/bidder.keras'


def test_own_generator_is_at_distance_zero_and_others_are_not():
    gen = rb.RuleSystemBidder(rb.Settings(), 'standard')
    bid_deal = lambda h, d, v: bid_table([gen] * 4, h, d, v)[0]
    own = card_distance(card_from_settings(asdict(rb.Settings()), 'rb-p'), bid_deal, deals=150, seed=3)
    other = card_distance('two-over-one', bid_deal, deals=150, seed=3)
    assert own['rate'] == 0 and own['residual'] == []
    assert other['rate'] > 0.1 and 'open_minor' in other['residual']


def test_detection_prefers_the_generator():
    gens = {'p': rb.RuleSystemBidder(rb.Settings(), 'standard'), 's': rb.RuleSystemBidder(rb.STANDARD, 'standard')}
    cands = [DeterministicProfile('p', gens['p']), DeterministicProfile('s', gens['s'])]
    profiles = cands + [UnknownMixture(cands)]
    ll = []
    for hands, dealer, vul in deals(40, 5):
        try:
            calls, _ = bid_table([gens['p']] * 4, hands, dealer, vul)
        except (ValueError, IndexError):
            continue
        b = board_loglik(profiles, hands, dealer, vul, calls, (0, 2))
        ll.append([b['p'], b['s'], b['unknown']])
    ll = np.array(ll)
    assert ll[:, 0].sum() > ll[:, 1].sum() and ll[:, 0].sum() > ll[:, 2].sum()
    reached = boards_to_identify(ll, 0, orderings=20)
    assert all(r is not None and r <= 20 for r in reached)
    d = experience_delta('pair-x', 'test/0', dict(zip(['p', 's', 'unknown'], ll[0])))
    from bridge_harness import experience as E
    store = E.add(E.empty('pair-x'), d)
    post = E.posterior(store['stats']['profile'], {'p': 1 / 3, 's': 1 / 3, 'unknown': 1 / 3})
    assert abs(sum(post.values()) - 1) < 1e-9


@pytest.mark.skipif(not GEN5.exists(), reason='restore models/bidding/gen5-2026-11-10 first (needs h5py)')
def test_net_profile_logits_reproduce_its_calls():
    pytest.importorskip('h5py')
    from bridge_harness.cards.match import NetProfile
    from bridge_harness.system_bidders import BenLstmBidder
    from bridge_harness.system_fit import simulate
    from bridge_harness.bidding_env import CALLS
    b, prof = BenLstmBidder(str(GEN5)), NetProfile('gen5', str(GEN5))
    ds = list(deals(30, 6))
    hands = np.array([d[0] for d in ds])
    sim = simulate([b, b], hands, np.array([d[1] for d in ds]), np.array([VULS.index(d[2]) for d in ds]))
    for i, (h, d, v) in enumerate(ds):
        calls = [CALLS[int(t)] for t in sim['calls'][i] if t >= 0]
        for p, c, n in prof.call_probs(h, d, v, calls, [0, 1, 2, 3]):
            assert max(p, key=p.get) == c


# ---- G9-B6: real cards -----------------------------------------------------------------------------
@pytest.mark.parametrize('cid', ['acbl-sayc', 'wbf-pryor-scerri', 'wbf-laukkanen-nordgren'])
def test_real_cards_compile_and_own_bidder_never_breaks(cid):
    card = load_card(cid)
    assert card.unsupported() == []
    prov = json.loads((_Path(__file__).resolve().parents[1] / 'configs' / 'cards' / f'{cid}.json').read_text())['provenance']
    assert prov['source'] and prov['confidence'] and 'not_placed' in prov
    b, f = CardBidder(cid), CardFactor(cid)
    for hands, dealer, vul in deals(60, 13):
        calls, _ = bid_table([b] * 4, hands, dealer, vul)
        for s in range(4):
            length, hon = hand_types(membership([hands[s]]))
            assert f.type_log_score(length, hon, s, dealer, vul, calls)[0] >= len(f.seat_terms(calls, dealer, s, vul)) * np.log(0.95) - 1e-9


# ---- shell hooks (g9: profile=, shell_reader, experience delta) ----------------------------------
def test_profile_keyword_restricts_to_residual():
    from bridge_harness.player_model import PlayerModel
    from bridge_harness.cards.factor import shell_reader, bidding_delta
    card = dict(json.loads((_Path(__file__).resolve().parents[1] / 'configs' / 'cards' / 'two-over-one.json').read_text()))
    card['residual'] = {'house-gen6': ['open_nt']}
    model = PlayerModel('pair', bidding=card)
    reader = shell_reader(model)
    hands = [h for d in deals(40, 21) for h in d[0]]
    length, hon = hand_types(membership(hands))
    auction = ['PASS', '1N', 'PASS', '2C', 'PASS', '2H']
    full = reader.type_log_score(length, hon, 1, 0, 'None', auction)
    res = reader.type_log_score(length, hon, 1, 0, 'None', auction, profile='house-gen6')
    unk = reader.type_log_score(length, hon, 1, 0, 'None', auction, profile='never-measured')
    only_nt = reader.log_score_features(hand_features(length, hon), 1, 0, 'None', auction, families={'open_nt'})
    assert np.allclose(res, only_nt) and np.allclose(unk, full) and not np.allclose(res, full)
    assert shell_reader(PlayerModel('plain')) is None
    # an experience delta, then a reader built from a snapshot of it
    from bridge_harness import experience as E
    store = E.empty('pair')
    b = CardBidder('two-over-one')
    for i, (hh, dealer, vul) in enumerate(deals(30, 22)):
        calls, _ = bid_table([b] * 4, hh, dealer, vul)
        store = E.add(store, bidding_delta('pair', f't/{i}', reader, hh, dealer, vul, calls, (0, 2)))
    assert any(k.startswith('bid.') for k in store['stats'])
    snap = E.snapshot(store, 's1')
    r2 = shell_reader(PlayerModel('pair', bidding=card, experience=snap))
    assert r2.dev.counts and all(d == 0 for a, d in r2.dev.counts.values())      # its own bidder never deviates
