"""Bidding styles (bridge_harness/bid_style.py) and personas (bridge_harness/persona.py). No models needed."""
import random
import statistics

import numpy as np
import pytest

from bridge_harness import bid_style as B, persona as P
from bridge_harness.bidding_env import CALLS, CALL_ID
from bridge_harness.core import parse_hand


def probs(**p):
    """A probability vector over CALLS from {call: p} (names with _ for nothing special: '1S', 'PASS')."""
    v = np.zeros(len(CALLS))
    for k, x in p.items():
        v[CALL_ID[k.replace('_', '')]] = x
    return v


def mask(*names):
    m = np.zeros(len(CALLS), bool)
    for n in names:
        m[CALL_ID[n]] = True
    return m


FLAT_TEN = parse_hand('KJ4.Q73.K852.J96')        # 10 HCP, 4333-ish
SHAPELY_EIGHT = parse_hand('AQ9852.KJ963.4.2')   # 10 HCP, 6-5-1-1
FLAT_FIFTEEN = parse_hand('AK4.KQ7.Q852.J96')    # 15 HCP flat


def test_check():
    assert B.check({'aggressive': 1, 'shape': -0.5, 'random': 0.1, 'near': 1}) == {'aggressive': 1, 'shape': -0.5, 'random': 0.1, 'near': 1}
    for bad in ({'tempo': 1}, {'aggressive': 5}, {'random': 1.5}, {'near': -1}, {'aggressive': True}):
        with pytest.raises(ValueError):
            B.check(bad)


def test_action():
    legal = ['PASS', 'X', '2S', '3S', '4S', '2N', '3N', '3H']
    assert B.action('PASS', legal) == 0
    assert B.action('X', legal) == 0.5
    assert B.action('2S', legal) == 1 and B.action('3S', legal) == 2 and B.action('4S', legal) == 3
    assert B.action('3N', legal) == 2 and B.action('3H', legal) == 1


def test_close_calls_and_direction():
    p, m = probs(PASS=0.5, **{'1S': 0.3, '2S': 0.05}), mask('PASS', '1S', '2S')
    assert B.close_calls(p, m, 0.0) == [CALL_ID['PASS']]
    assert B.close_calls(p, m, 1.0) == [CALL_ID['PASS'], CALL_ID['1S']]           # 0.3 >= 0.5 / e
    agg, con = {'aggressive': 1, 'near': 1}, {'aggressive': -1, 'near': 1}
    assert CALLS[B.choose(p, m, FLAT_TEN, agg, 0.9, 0.)] == '1S'
    assert CALLS[B.choose(p, m, FLAT_TEN, con, 0.9, 0.)] == 'PASS'
    assert CALLS[B.choose(p, m, FLAT_TEN, {'near': 1}, 0.9, 0.)] == 'PASS'        # no direction: the bidder's best
    # outside the margin nothing changes, whatever the style
    assert CALLS[B.choose(p, m, FLAT_TEN, {'aggressive': 4, 'near': 0.3}, 0.9, 0.)] == 'PASS'


def test_weight_is_an_exchange_rate():
    # 1S is 0.6 times as likely as PASS (log ratio 0.51) and one step more action; 2S is 0.3 times (1.20), two steps
    p, m = probs(PASS=0.5, **{'1S': 0.3, '2S': 0.15}), mask('PASS', '1S', '2S')
    pick = lambda a: CALLS[B.choose(p, m, FLAT_TEN, {'aggressive': a, 'near': 3}, 0.9, 0.)]
    assert pick(0.4) == 'PASS'          # 0.4 < 0.51: not worth it
    assert pick(0.55) == '1S'           # one step is worth 0.55 > 0.51; two steps 1.10 < 1.20
    assert pick(0.7) == '2S'            # two steps 1.40 > 1.20
    # a reader told half of a 0.7 style (0.35) expects the bidder's own PASS, not 2S
    full, half = {'aggressive': 0.7, 'near': 3}, B.scaled({'aggressive': 0.7, 'near': 3}, 0.5)
    assert max(B.distribution(p, m, FLAT_TEN, full).items(), key=lambda kv: kv[1])[0] == CALL_ID['2S']
    assert max(B.distribution(p, m, FLAT_TEN, half).items(), key=lambda kv: kv[1])[0] == CALL_ID['PASS']


def test_random_share_and_distribution():
    p, m = probs(PASS=0.5, **{'1S': 0.3, '2S': 0.25}), mask('PASS', '1S', '2S')
    style = {'aggressive': -1, 'random': 0.3, 'near': 1}
    d = B.distribution(p, m, FLAT_TEN, style)
    assert abs(sum(d.values()) - 1) < 1e-12
    # the random 0.3 is spread by the bidder's own probabilities (0.5, 0.3, 0.25 of 1.05); the directed call is PASS
    assert abs(d[CALL_ID['PASS']] - (0.7 + 0.3 * 0.5 / 1.05)) < 1e-12 and abs(d[CALL_ID['2S']] - 0.3 * 0.25 / 1.05) < 1e-12
    rng = random.Random(3)
    picks = [B.choose(p, m, FLAT_TEN, style, rng.random(), rng.random()) for _ in range(20000)]
    for i, q in d.items():
        assert abs(picks.count(i) / len(picks) - q) < 0.015


def test_shape_lean_follows_the_hand():
    assert B.lean(SHAPELY_EIGHT, 1) > 0.5 and B.lean(FLAT_TEN, 1) < 0
    assert B.lean(FLAT_FIFTEEN, -1) > 0.5 and B.lean(FLAT_TEN, -1) == 0.
    p, m = probs(PASS=0.5, **{'1S': 0.4}), mask('PASS', '1S')
    shape = {'shape': 1, 'near': 1}
    assert CALLS[B.choose(p, m, SHAPELY_EIGHT, shape, 0.9, 0.)] == '1S'         # shapely: bids
    assert CALLS[B.choose(p, m, FLAT_TEN, shape, 0.9, 0.)] == 'PASS'            # flat: passes
    points = {'shape': -1, 'near': 1}
    assert CALLS[B.choose(p, m, FLAT_FIFTEEN, points, 0.9, 0.)] == '1S'


def test_distribution_point_moments():
    mean, sd = B.compute_d_moments()
    assert abs(mean - B.D_MEAN) < 1e-3 and abs(sd - B.D_SD) < 1e-3


def test_scaled():
    assert B.scaled({'aggressive': 1, 'shape': -1, 'random': 0.1, 'near': 1}, 0.5) == {'aggressive': 0.5, 'shape': -0.5, 'random': 0.1, 'near': 1}


def test_persona_dials():
    rng = random.Random(7)
    ps = [P.draw(rng, bid_near=1.0) for _ in range(3000)]
    for p in ps:
        assert -0.2 <= p['correlation'] <= 0.8
        for d in P.DIMENSIONS:
            assert 0 <= p['knowledge'][d] <= 0.8
            assert 0 <= p['disclosure'][d] <= 1.5 * p['knowledge'][d] + 1e-9
        assert set(p['play_style']) == set(P.PLAY) | {'random'} and set(p['bid_style']) == set(P.BID) | {'random', 'near'}
    ratios = [p['disclosure'][d] / p['knowledge'][d] for p in ps for d in P.DIMENSIONS if p['knowledge'][d] > 0.05]
    assert 0.70 < statistics.mean(ratios) < 0.80            # usually 75% (triangular 0, 0.75, 1.5: mean 0.75)
    a = [p['knowledge']['tempo'] for p in ps]
    b = [p['knowledge']['aggressive'] for p in ps]
    assert 0.25 < float(np.corrcoef(a, b)[0, 1]) < 0.55     # correlated across dimensions (rho mode 0.6, mean 0.4)
    v = P.view(ps[0], 'partner')
    assert v['bid_style']['aggressive'] == pytest.approx(ps[0]['bid_style']['aggressive'] * ps[0]['knowledge']['aggressive'])
    assert v['bid_style']['near'] == ps[0]['bid_style']['near']
    assert isinstance(P.disclosure_text(ps[0]), str)


def test_partnerships():
    rng = random.Random(11)
    pairs = [P.draw_partnership(rng) for _ in range(4000)]
    for a, b in pairs[:50]:
        assert a['correlation'] == b['correlation']                 # one correlation across dimensions per partnership
        assert a['bid_style']['near'] == b['bid_style']['near'] == 6.0
    # partners' matching draws: latent correlation 0.5, so the uniform weights' correlation is 6/pi asin(1/4) = 0.483
    for key, d in (('play_style', 'tempo'), ('bid_style', 'aggressive'), ('knowledge', 'high')):
        x = [a[key][d] for a, _ in pairs]
        y = [b[key][d] for _, b in pairs]
        assert 0.40 < float(np.corrcoef(x, y)[0, 1]) < 0.56, (key, d)
    # each persona alone is distributed as before: weights uniform on [-1, 1] (play) and [-3, 3] (bidding)
    t = [a['play_style']['tempo'] for a, _ in pairs]
    assert abs(statistics.mean(t)) < 0.04 and 0.30 < statistics.pvariance(t) < 0.37        # uniform: 1/3
    ag = [b['bid_style']['aggressive'] for _, b in pairs]
    assert min(ag) >= -3 and max(ag) <= 3 and 2.7 < statistics.pvariance(ag) < 3.3          # uniform on +-3: 3
    # opposing partnerships are independent
    s = [P.seats(rng) for _ in range(3000)]
    x = [q[0]['play_style']['tempo'] for q in s]
    y = [q[1]['play_style']['tempo'] for q in s]
    z = [q[2]['play_style']['tempo'] for q in s]
    assert abs(float(np.corrcoef(x, y)[0, 1])) < 0.06 and float(np.corrcoef(x, z)[0, 1]) > 0.40


def test_identifier_and_public():
    assert P.is_variable('SidVariable') and not P.is_variable('stu4c-put') and not P.is_variable(None)
    assert P.is_variable('g8-variable', extra=['g8-variable'])
    pub = P.public()
    assert pub['identifier'] == 'SidVariable' and pub['partner_correlation'] == 0.5 and pub['bid']['near'] == 6.0
    p = P.draw(random.Random(5))
    assert isinstance(P.describe(p, 'partner'), str) and isinstance(P.describe(p, 'full'), str)
    assert P.disclosure_text(p) == P.describe(p, 'opponent')
