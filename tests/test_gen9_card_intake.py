"""Card intake v0 (G9-B8): variants by seat and vulnerability, recorded agreements, the new fields, the sample cards."""
import importlib.util
import json
from pathlib import Path

import pytest

from bridge_harness.cards.bidder import CardBidder, bid_table
from bridge_harness.cards.card import LATER_FIELDS, builtin_ids, load_card, vul_matches
from bridge_harness.cards.context import Context
from bridge_harness.cards.features import features_of_hands
from bridge_harness.cards.system import CardSystem

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = [ROOT / 'configs/cards/intake/sample-a-acbl.json', ROOT / 'configs/cards/intake/sample-a-wbf.json']


def hand(text):
    """'S:KQ5 H:KQ8 D:J9843 C:AK' to card ids (suit-major, 2..A)."""
    ids = []
    for part in text.split():
        suit, cards = part.split(':')
        ids += [('SHDC'.index(suit)) * 13 + '23456789TJQKA'.index(c) for c in cards]
    return sorted(ids)


def call(system, calls, dealer, seat, vul, h):
    f = features_of_hands([hand(h)])
    rules = system.rules(Context.make(calls, dealer, seat, vul))
    return next(r for r in rules if r.pred.dist(f)[0] == 0).call


CARD = {
    'id': 'variants-test',
    'variants': [
        {'when': {'seats': [1], 'vul': 'fav', 'scoring': 'imps'},
         'descriptor': {'open.three_level': {'len': 6, 'len_max': 7, 'hcp_min': 0, 'hcp_max': 10}, 'open.weak_quality': 0}},
        {'when': {'vul': 'we'}, 'descriptor': {'open.weak_top3': 2}},
        {'when': {'seats': [4]}, 'descriptor': {'open.two': {'2H': {'type': 'weak', 'hcp': [8, 10], 'len': [6, 6]}}}},
        {'when': {'seats': [4]}, 'descriptor': {'open.two': {'2H': {'type': 'weak', 'hcp': [9, 10], 'len': [6, 6]}}}},
    ],
}


def test_vul_matches():
    assert vul_matches('fav', False, True) and not vul_matches('fav', False, False)
    assert vul_matches('unfav', True, False) and vul_matches('we', True, True) and not vul_matches('nv', True, False)
    assert vul_matches('both', True, True) and vul_matches('none', False, False) and vul_matches('any', True, False)


def test_at_resolves_seat_vulnerability_and_scoring():
    c = load_card(CARD)
    assert c.unsupported() == []
    assert c.at(1, False, False) is c                                     # nothing applies
    fav = c.at(1, False, True)
    assert fav.variant == (0,) and fav['open']['three_level']['len'] == 6 and fav['open']['weak_quality'] == 0
    assert c.at(1, False, True, scoring='mp') is c                        # an IMPs-only variant
    assert c.at(2, False, True) is c                                      # first seat only
    assert c.at(3, True, False)['open']['weak_top3'] == 2
    assert c.at(4, False, False)['open']['two']['2H']['hcp'] == [9, 10]  # the later of two matching variants wins
    assert c.at(4, False, False)['open']['two']['2S']['hcp'] == [5, 10]  # other calls keep the base spec
    assert c['open']['three_level']['len'] == 7                           # the base card is unchanged


def test_variant_errors_are_reported_or_raised():
    c = load_card({'id': 'x', 'variants': [{'when': {'vul': 'we'}, 'descriptor': {'open.bogus': 1}}]})
    assert c.unsupported() == ['variants[0].open.bogus']
    with pytest.raises(ValueError):
        load_card({'id': 'x', 'variants': [{'when': {'vul': 'sometimes'}, 'descriptor': {'open.min_hcp': 13}}]})
    with pytest.raises(ValueError):
        load_card({'id': 'x', 'variants': [{'when': {'seat': [1]}, 'descriptor': {'open.min_hcp': 13}}]})
    with pytest.raises(ValueError):
        load_card({'id': 'x', 'variants': [{'when': {'seats': [5]}, 'descriptor': {'open.min_hcp': 13}}]})


def test_recorded_keys_are_checked_against_the_field_list():
    c = load_card({'id': 'x', 'recorded': {'resp.major.drury': 'reverse', 'resp.major.nonsense': True}})
    assert c.unsupported() == ['recorded.resp.major.nonsense']
    assert c.recorded['resp.major.drury'] == 'reverse'


def test_compiled_calls_follow_the_variants():
    s = CardSystem(load_card(CARD))
    junk = 'S:J98765 H:432 D:32 C:32'                  # one honour, 1 HCP
    assert call(s, [], 0, 0, 'EW', junk) == '3S'       # North first seat, favourable: very light
    assert call(s, [], 0, 0, 'None', junk) == 'PASS'
    assert call(s, ['PASS'], 0, 1, 'NS', junk) == 'PASS'   # East second seat, favourable: not first seat
    weak = 'S:32 H:KJ9876 D:Q32 C:32'                  # one of the top three hearts
    assert call(s, [], 0, 0, 'None', weak) == '2H'
    assert call(s, [], 0, 0, 'Both', weak) == 'PASS'   # vulnerable: two of the top three
    assert call(s, ['PASS'] * 3, 0, 3, 'None', weak) == 'PASS'                     # fourth seat: 9-10
    assert call(s, ['PASS'] * 3, 0, 3, 'None', 'S:32 H:KQ9876 D:K32 C:J2') == '2H'


def test_balancing_nt_major_and_woolsey():
    s = CardSystem(load_card({'id': 'x', 'comp.balancing_nt_major': [11, 16], 'comp.vs_nt': 'woolsey'}))
    bal16 = 'S:K32 H:AJ4 D:K432 C:KJ2'                 # 16 HCP, balanced, hearts stopped
    assert call(s, ['1H', 'PASS', 'PASS'], 0, 3, 'None', bal16) == '1N'
    assert call(s, ['1D', 'PASS', 'PASS'], 0, 3, 'None', 'S:K32 H:AJ4 D:KQ32 C:K32') != '1N'   # 16 over a minor: not 1NT
    assert call(s, ['1N'], 0, 1, 'None', 'S:KJ93 H:32 D:AQ976 C:32') == 'X'      # a major and a longer minor
    assert call(s, ['1N'], 0, 1, 'None', 'S:KJ93 H:QJ93 D:A97 C:32') == '2C'     # both majors
    assert call(s, ['1N'], 0, 1, 'None', 'S:KQJ932 H:32 D:A97 C:32') == '2D'     # one six-card major
    assert call(s, ['1N'], 0, 1, 'None', 'S:KQJ93 H:32 D:A976 C:32') == '2S'     # five spades and four of a minor


def test_identities_of_older_cards_do_not_see_later_fields():
    for cid in builtin_ids():
        doc = load_card(cid).identity_doc()
        assert 'variants' not in doc
        for (sec, key) in LATER_FIELDS:
            assert key not in doc['card'][sec]
    a, b = CardBidder(load_card(CARD)), CardBidder(load_card(dict(CARD, variants=CARD['variants'][:1])))
    assert a.sha256 != b.sha256


@pytest.mark.parametrize('path', SAMPLES, ids=lambda p: p.stem)
def test_sample_cards_load_compile_and_keep_their_own_auctions(path):
    card = load_card(json.loads(path.read_text()))
    assert card.unsupported() == []
    assert len(card.variants) == 4 and card.style and card.recorded
    statuses = {s['status'] for s in card.style}
    assert statuses <= {'field', 'variant', 'default', 'not_placed', 'recorded'}
    b = CardBidder(card)
    import random
    rng = random.Random(5)
    vuls = ('None', 'NS', 'EW', 'Both')
    for i in range(60):
        deck = list(range(52))
        rng.shuffle(deck)
        hands = [sorted(deck[13 * k:13 * k + 13]) for k in range(4)]
        calls, _ = bid_table([b] * 4, hands, i % 4, vuls[i // 4 % 4])
        assert calls


def test_intake_tool_decodes_symbol_font_suits():
    spec = importlib.util.spec_from_file_location('intake', ROOT / 'scripts/gen9_card_intake.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.decode('1 3, 1 3, 2, 2') == '1♣ 3, 1♦ 3, 2♥, 2♠'
    found = m.style_candidates(['Sound Vul. 1st NV vs. V joke', 'STAYMAN, TRANSFERS'], 'card')
    assert [s['text'] for s in found] == ['Sound Vul.', '1st NV vs. V joke']
