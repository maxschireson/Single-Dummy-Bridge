"""The rule bidder (bridge_harness/rule_bidder.py): legal and finite auctions, the system's opening structure,
and the meanings the tables give to calls."""
import unittest

import numpy as np

from bridge_harness import rule_bidder as R
from bridge_harness.bidding_env import CALLS, legal_mask
from bridge_harness.core import auction_contract


def deal(seed, i):
    rng = np.random.default_rng([seed, i])
    deck = rng.permutation(52)
    return tuple(tuple(sorted(map(int, deck[13 * s:13 * s + 13]))) for s in range(4)), int(rng.integers(4)), int(rng.integers(4))


def auction(hands, dealer, vul, sides):
    calls = []
    for _ in range(100):
        seat = (dealer + len(calls)) % 4
        token = sides[seat % 2].call(hands[seat], seat, dealer, vul, calls)
        assert legal_mask(dealer, [CALLS[c] for c in calls])[token], (CALLS[token], [CALLS[c] for c in calls])
        calls.append(token)
        try:
            return calls, auction_contract(dealer, [CALLS[c] for c in calls])
        except ValueError as e:
            if str(e) != 'Incomplete auction':
                raise
    raise AssertionError('the auction did not end')


class RuleBidderTests(unittest.TestCase):
    def test_every_call_is_legal_and_every_auction_ends(self):
        precision, standard = R.RuleSystemBidder(), R.RuleSystemBidder(R.STANDARD, opponents=R.Settings())
        both = R.RuleSystemBidder(opponents='same')
        lengths = []
        for i in range(300):
            hands, dealer, vul = deal(11, i)
            for sides in ((precision, standard), (standard, precision), (both, both)):
                calls, contract = auction(hands, dealer, vul, sides)
                lengths.append(len(calls))
                if contract is not None:
                    self.assertLessEqual(contract.level, 7)
        self.assertLess(max(lengths), 40)
        self.assertGreater(np.mean(lengths), 5)

    def test_it_is_a_function_of_hand_and_auction(self):
        a, b = R.RuleSystemBidder(), R.RuleSystemBidder()
        self.assertEqual(a.sha256, b.sha256)
        self.assertNotEqual(a.sha256, R.RuleSystemBidder(dict(club_min=17)).sha256)
        for i in range(60):
            hands, dealer, vul = deal(12, i)
            first, _ = auction(hands, dealer, vul, (a, a))
            again, _ = auction(hands, dealer, vul, (b, b))
            self.assertEqual(first, again)
            for k in range(len(first)):                 # asked out of order, with a cold cache, it says the same
                seat = (dealer + k) % 4
                self.assertEqual(R.RuleSystemBidder().call(hands[seat], seat, dealer, vul, first[:k]), first[k])

    def test_precision_openings(self):
        b = R.RuleSystemBidder()
        g = b.settings
        seen = {}
        for i in range(4000):
            hands, _, vul = deal(13, i)
            h = R.Hand(hands[0])
            token = b.call(hands[0], 0, 0, vul, [])
            seen.setdefault(token, []).append(h)
            if h.hcp >= g.club_min:
                self.assertEqual(token, R.bid(1, R.C))
        for h in seen[R.bid(1, R.C)]:
            self.assertGreaterEqual(h.hcp, g.club_min)
        for h in seen[R.bid(1, R.N)]:
            self.assertTrue(g.nt_lo <= h.hcp <= g.nt_hi and h.balanced)
        for token, suit in ((R.bid(1, R.H), R.H), (R.bid(1, R.S), R.S)):
            for h in seen[token]:
                self.assertTrue(h.len[suit] >= 5 and g.open_min - g.open_light <= h.hcp <= g.limited_max)
        for h in seen[R.bid(2, R.C)]:
            self.assertTrue(h.len[R.C] >= g.two_clubs_len and h.hcp <= g.limited_max)
        for h in seen[R.bid(1, R.D)]:
            self.assertTrue(h.hcp <= g.limited_max and max(h.len[R.H], h.len[R.S]) <= 4)
        self.assertGreater(len(seen[R.bid(1, R.D)]), 100)
        self.assertGreater(len(seen[R.bid(2, R.D)]), 3)

    def test_the_negative_response_and_what_calls_show(self):
        b = R.RuleSystemBidder(opponents='same')
        told = b.describe(0, 0, 0, [R.bid(1, R.C), R.PASS, R.bid(1, R.D), R.PASS])
        self.assertEqual(told[0]['hcp'][0], b.settings.club_min)
        self.assertEqual((told[0]['kind'], told[0]['force']), ('strong', 1))
        self.assertEqual(told[2]['hcp'], (0, b.settings.neg_max))
        told = b.describe(2, 0, 0, [R.bid(1, R.N), R.PASS])
        self.assertEqual(told[0]['hcp'], (b.settings.nt_lo, b.settings.nt_hi))
        checked = 0
        for i in range(400):                            # a call from the tables fits the meaning the tables give it
            hands, dealer, vul = deal(14, i)
            calls, _ = auction(hands, dealer, vul, (b, b))
            first_bid = next((k for k, c in enumerate(calls) if c >= 5), None)
            if first_bid is None:
                continue
            m = b.describe((dealer + first_bid + 1) % 4, dealer, vul, calls[:first_bid + 1])[first_bid]
            h = R.Hand(hands[(dealer + first_bid) % 4])
            self.assertTrue(m['hcp'][0] <= h.hcp <= m['hcp'][1], (m, h.hcp))
            for suit, (lo, hi) in m['lengths'].items():
                self.assertTrue(lo <= h.len['CDHS'.index(suit)] <= hi)
            checked += 1
        self.assertGreater(checked, 300)

    def test_settings_are_checked_and_standard_is_natural(self):
        with self.assertRaises(ValueError):
            R.Settings(style='acol')
        with self.assertRaises(ValueError):
            R.Settings(nt_lo=17, nt_hi=15)
        natural = R.RuleSystemBidder(R.STANDARD)
        strong = 0
        for i in range(1500):
            hands, _, vul = deal(15, i)
            h = R.Hand(hands[0])
            token = natural.call(hands[0], 0, 0, vul, [])
            if token == R.bid(1, R.C):
                self.assertTrue(h.len[R.C] >= 3 and h.hcp <= 21)
            strong += token == R.bid(2, R.C)
        self.assertGreater(strong, 0)


if __name__ == '__main__':
    unittest.main()
