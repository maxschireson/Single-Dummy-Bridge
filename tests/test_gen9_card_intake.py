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


def test_intake_tool_reads_form_fields(tmp_path):
    pymupdf = pytest.importorskip('pymupdf')
    spec = importlib.util.spec_from_file_location('intake', ROOT / 'scripts/gen9_card_intake.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((40, 72), 'Negative', fontsize=9)
    page.insert_text((40, 102), '1NT', fontsize=9)
    for name, kind, rect, value in (('neg_dbl', pymupdf.PDF_WIDGET_TYPE_CHECKBOX, (90, 63, 99, 72), True),
                                    ('nt_lo', pymupdf.PDF_WIDGET_TYPE_TEXT, (60, 92, 90, 104), '15'),
                                    ('nt_hi', pymupdf.PDF_WIDGET_TYPE_TEXT, (100, 92, 130, 104), '')):
        w = pymupdf.Widget()
        w.field_type, w.field_name, w.rect, w.field_value = kind, name, pymupdf.Rect(*rect), value
        page.add_widget(w)
    pdf = tmp_path / 'form.pdf'
    doc.save(str(pdf))
    (tmp_path / 'pages').mkdir()
    pages = m.pdf_pages(pdf, tmp_path, 72)
    got = {f['name']: f for f in pages[0]['fields']}
    assert got['neg_dbl']['value'] is True and got['neg_dbl']['label'] == 'Negative'
    assert got['nt_lo']['value'] == '15' and got['nt_lo']['label'] == '1NT'
    assert got['nt_hi']['value'] == ''


def test_five_card_weak_twos_in_third_seat():
    """'can preempt 5 card suits': a variant for third seat, the base keeps six cards."""
    c = load_card({'id': 'x', 'variants': [{'when': {'seats': [3]}, 'descriptor': {'open.two': {
        '2H': {'type': 'weak', 'hcp': [5, 10], 'len': [5, 6]}, '2S': {'type': 'weak', 'hcp': [5, 10], 'len': [5, 6]}}}}]})
    s = CardSystem(c)
    five = 'S:KQT93 H:32 D:J32 C:432'                    # 6 HCP, five good spades
    assert call(s, [], 0, 0, 'None', five) == 'PASS'
    assert call(s, ['PASS', 'PASS'], 0, 2, 'None', five) == '2S'


def test_derived_one_nt_rebid_range():
    """G9-B10 item 4: the opener's 1NT rebid range, derived from the 1NT opening when the card does not state it."""
    def rnt(**kw):
        return CardSystem(load_card({'id': 'x', **kw})).rebid_nt(1, False)
    assert rnt(**{'open.nt': [{'hcp': [14, 16]}], 'open.min_hcp': 11}) == (11, 13)
    assert rnt(**{'open.nt': [{'hcp': [14, 17]}], 'open.min_hcp': 12}) == (12, 13)
    assert rnt(**{'open.nt': [{'hcp': [12, 14]}], 'open.min_hcp': 12}) == (15, 17)     # weak notrump: the range above, as before
    assert rnt(**{'open.nt': [{'hcp': [15, 17]}], 'open.min_hcp': 12}) == (12, 14)     # strong notrump, as before
    assert rnt(**{'open.nt': [{'hcp': [14, 16]}], 'open.min_hcp': 11, 'rebid.one_nt': [12, 14]}) == (12, 14)   # a stated range wins


def test_built_in_cards_keep_their_rebid_ranges():
    """Only rb-precision derives a different range (17-17 before, 11-13 now, which is what the rule bidder rebids 1NT
    with: balanced 11 to 13 on 175 of 6,000 deals, seed 9301), and its card does not cover rebids, so no built-in card
    bids or reads differently."""
    want = {'acbl-sayc': (12, 14), 'acol': (15, 17), 'house-gen5-fit': (11, 14), 'polish-club': (12, 14),
            'precision': (11, 13), 'rb-precision': (11, 13), 'rb-standard': (11, 14), 'sayc': (12, 14),
            'two-over-one': (12, 14), 'wbf-laukkanen-nordgren': (11, 14), 'wbf-pryor-scerri': (12, 14)}
    got = {cid: CardSystem(load_card(cid)).rebid_nt(1, False) for cid in builtin_ids()}
    assert {k: got[k] for k in want} == want
    assert 'rebid' not in load_card('rb-precision').d['cover']
