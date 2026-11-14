"""The post-hand analysis on two deals of the strategy-fusion set (experiments/sure_tricks/fusion_deals.json at 2e6ed6d):
6S by South, AJ5 opposite K104 in diamonds, a sure strip and club exit.

Needs DDS built in the repository (python scripts/build_dds.py) and play/native/sure_cpp
(g++ -O2 -std=c++17 -o play/native/sure_cpp play/native/sure.cpp). Skipped otherwise.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT.parent)]

from bridge_harness.core import card, parse_hand   # noqa: E402
from sidplay import analysis as A   # noqa: E402

try:
    from bridge_harness.dds import DDS
    DDS_ = DDS(cache_path='')
except Exception:                     # DDS not built
    DDS_ = None
needs = pytest.mark.skipif(DDS_ is None or not A.Sure().available(), reason='DDS or sure_cpp not built')

A6_QE = ["KQ872.A4.KT4.A73", "3.87652.Q862.QT8", "AJT94.K3.AJ5.K64", "65.QJT9.973.J952"]    # diamond queen East
A6_QW = ["KQ872.A4.KT4.A73", "3.87652.9862.QT8", "AJT94.K3.AJ5.K64", "65.QJT9.Q73.J952"]    # diamond queen West


def play_out(hands, forced):
    """Declarer's cards as forced (by index in the play); every other card the lowest double-dummy best."""
    st = A.State(hands, 0, 2)
    play = []
    while st.done_tricks < 13:
        n = len(play)
        if n in forced:
            c = card(forced[n])
        else:
            v, _ = DDS_.solve(st.dd_hands(), 0, st.leader, list(st.trick))
            c = min(x for x, y in v.items() if y == max(v.values()))
        play.append((st.mover, c))
        st.play(c)
    return play


@needs
def test_guarantee_given_away_without_a_double_dummy_loss():
    """The sound line to trick 6, then dummy leads a diamond instead of exiting with the third club. Double dummy
    nothing is lost (declarer still guesses the queen), but the contract was guaranteed and the diamond gave that up:
    with 7 cards left the spade and club cards guarantee 12 and every diamond 11 (README section 5 on that branch)."""
    hands = [parse_hand(h) for h in A6_QE]
    play = play_out(hands, {0: 'HQ', 1: 'H4', 3: 'HK', 4: 'SA', 6: 'S2', 8: 'S4', 10: 'SK', 12: 'HA', 14: 'H3',
                            16: 'C3', 18: 'CK', 20: 'C4', 22: 'CA', 24: 'D4', 26: 'DA'})
    out = A.analyse(hands, '6S', 2, play, [2], dds=DDS_)
    assert out['tricks'] == 12 and out['dd_start'] == 12 and out['lost'] == []
    kinds = [(e['kind'], e['trick']) for e in out['events']]
    assert ('had_guarantee', 1) in kinds
    gave = [e for e in out['events'] if e['kind'] == 'gave_away']
    assert len(gave) == 1 and gave[0]['trick'] == 7 and gave[0]['card'] == 'D4'
    assert {'S7', 'SQ', 'C7'} <= set(gave[0]['keep']) and not any(k[0] == 'D' for k in gave[0]['keep'])
    # Before East has followed to trick 1 nothing is guaranteed: East might be void in hearts.
    first = out['cards'][1]
    assert first['seat'] == 'N' and first['sure']['makes'] is False
    # A guarantee never exceeds the double-dummy value on the real layout.
    for r in out['cards']:
        s = r.get('sure')
        if s and s.get('mode') == 'tricks':
            assert s['guaranteed'] <= r['dd']
    assert out['summary'] == dict(side_start=12, side_end=12, lost=0, partner_lost=0, gifts=0)


@needs
def test_finesse_explained_by_the_queen():
    """Trumps drawn, then a diamond to the jack with the queen West. The diamond lead already gave away the
    guarantee; the jack itself kept what was still sure, and it lost a trick because of where the queen was."""
    hands = [parse_hand(h) for h in A6_QW]
    play = play_out(hands, {0: 'HQ', 1: 'H4', 3: 'HK', 4: 'SA', 6: 'S2', 8: 'S4', 10: 'SK', 12: 'D4', 14: 'DJ'})
    out = A.analyse(hands, '6S', 2, play, [2], dds=DDS_)
    assert out['tricks'] == 11
    gave = [e for e in out['events'] if e['kind'] == 'gave_away']
    assert [(e['trick'], e['card']) for e in gave] == [(4, 'D4')]
    (lost,) = out['lost']
    assert lost['card'] == 'DJ' and lost['loss'] == 1 and lost['kind'] == 'layout'
    assert '♦Q' in lost['text'] and 'East' in lost['text'] and lost['exchanges']['complete']
    assert out['summary']['lost'] == 1 and out['summary']['side_start'] - out['summary']['side_end'] == 1


@needs
def test_defender_focus_and_budget():
    """South's decisions as a defender get declarer's guarantee after each card South could play; a zero budget
    skips the sure-trick search and still returns the double-dummy accounting."""
    hands = [parse_hand(h) for h in A6_QE]
    # 6S by West in the rotated sense is awkward to build here; use 6S by North-South and East as the focus defender.
    play = play_out(hands, {})
    out = A.analyse(hands, '6S', 2, play, [1], dds=DDS_)
    defending = [r['sure'] for r in out['cards'] if r.get('sure')]
    assert defending and all(s['kind'] == 'defending' for s in defending)
    assert all(r['by'] == 'E' for r in out['cards'] if r.get('sure'))
    out = A.analyse(hands, '6S', 2, play, [2], dds=DDS_, limits=dict(sure_budget=0))
    assert not any(r.get('sure') for r in out['cards']) and out['engines']['sure_skipped']['budget'] > 0
    assert len(out['cards']) == 52 and out['tricks'] == 12


def test_sure_line_rotation():
    """East-West declaring is rotated so that the declaring side sits North-South for sure_cpp."""
    hands = [parse_hand(h) for h in A6_QE]
    rotated = hands[3:] + hands[:3]          # every hand one seat to the left: South's hand is now West's
    st_ns, st_ew = A.State(hands, 0, 2), A.State(rotated, 0, 3)
    assert A.sure_line(st_ns) == A.sure_line(st_ew)
