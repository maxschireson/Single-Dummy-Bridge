"""Richard Pavlicek's fifty trump strip squeeze endings (study 9Q53, rpbridge.net/9q53.htm) against the winning-line
logic (bridge_harness/x8_claims.py and the solver sure_cpp). Max, 14 November 2026: "he has a bunch of trump strip
squeezes. Make test deals for each of them (a few per) and make sure our guarantee logic finds all of them. But do not
train the net on them."

TEST POSITIONS ONLY (tests/squeeze_endings.json): they are not deals of any collection and never reach a training set.

What "finds" can mean. The logic guarantees a number of tricks against every lie of the unseen cards, given the hand
sizes and the show-outs: what declarer can know for certain. A squeeze diagram shows one lie. So:

  as drawn      Declarer told every show-out the diagram allows. Five of the fifty are then guaranteed in full. In the
                other forty-five the count depends on which defender holds particular cards of a suit both still hold;
                show-outs cannot settle that, and the logic guarantees fewer tricks, as it must.
  marked        Versions in which show-outs fix every card: a defender's cards in a suit both hold are replaced by unused
                low cards of a suit only he holds, kept only where double dummy rates every lead of South's as in the
                diagram. Twenty-five such versions exist, for twenty of the fifty techniques. There the guaranteed
                count must be Pavlicek's, and every lead must be rated as double dummy rates it.
  renamed       Each of those with the suits renamed (the trump suit too): nothing may change.

The diagrams themselves are checked against double dummy: his count and his lead in all fifty.
"""
import json
import os
from pathlib import Path
import unittest

from bridge_harness import x8_claims
from bridge_harness.core import SEATS

BIN = os.environ.get('SURE_BIN', '')
HAVE_SOLVER = bool(BIN) and os.path.isfile(BIN) and os.access(BIN, os.X_OK)
try:
    from bridge_harness.dds import DDS
    DOUBLE_DUMMY = DDS()
except (RuntimeError, OSError):
    DOUBLE_DUMMY = None

DATA = json.loads(Path(__file__).with_name('squeeze_endings.json').read_text())
RANKS = '23456789TJQKA'
N, E, S, W = (SEATS.index(x) for x in 'NESW')
FOUND_AS_DRAWN = [11, 32, 37, 42, 47]
RENAMES = ((1, 0, 2, 3), (3, 2, 1, 0), (0, 2, 3, 1))        # new suit of each old suit; the trump suit moves with it


def cards(text, rename=(0, 1, 2, 3)):
    return sorted(13 * rename[suit] + RANKS.index(r) for suit, ranks in enumerate(text.split('.')) for r in ranks if r != '-')


def card(text, rename=(0, 1, 2, 3)):
    return 13 * rename['SHDC'.index(text[0])] + RANKS.index(text[1])


def voids(hand):
    return sum(1 << suit for suit in range(4) if not any(x // 13 == suit for x in hand))


def position(e, west=None, east=None, rename=(0, 1, 2, 3), told=True):
    """(solver line, the four hands by seat, trump) for an ending: South on lead, spades (renamed) trumps. `told`: each
    defender has shown out of every suit he holds none of."""
    hands = {N: cards(e['north'], rename), S: cards(e['south'], rename),
             W: cards(west or e['west'], rename), E: cards(east or e['east'], rename)}
    trump = rename[0]
    text = x8_claims.line(trump, 2, x8_claims.mask(hands[N]), x8_claims.mask(hands[S]), x8_claims.mask(hands[E] + hands[W]),
                          len(hands[E]), len(hands[W]), voids(hands[E]) if told else 0, voids(hands[W]) if told else 0)
    return text, hands, trump


def double_dummy(hands, trump):
    values, _ = DOUBLE_DUMMY.solve([hands[seat] for seat in range(4)], trump, S, [])
    return values


class Diagrams(unittest.TestCase):
    def test_fifty_endings_with_whole_hands(self):
        endings = DATA['endings']
        self.assertEqual([e['n'] for e in endings], list(range(1, 51)))
        for e in endings:
            _, hands, _ = position(e)
            every = [x for hand in hands.values() for x in hand]
            self.assertEqual({len(hand) for hand in hands.values()}, {e['of']}, e['n'])
            self.assertEqual(len(set(every)), len(every), e['n'])
            self.assertIn(card(e['lead']), hands[S], e['n'])
            for m in e['marked']:
                _, marked, _ = position(e, m['west'], m['east'])
                again = [x for hand in marked.values() for x in hand]
                self.assertEqual((len(set(again)), len(marked[W]), len(marked[E])), (len(again), e['of'], e['of']), e['n'])
                self.assertFalse(any(any(x // 13 == y // 13 for y in marked[E]) for x in marked[W]), e['n'])   # no suit with both

    @unittest.skipUnless(DOUBLE_DUMMY, 'DDS is not built')
    def test_double_dummy_agrees_with_his_count_and_his_lead(self):
        for e in DATA['endings']:
            _, hands, trump = position(e)
            values = double_dummy(hands, trump)
            self.assertEqual(max(values.values()), e['win'], e['n'])
            self.assertEqual(values[card(e['lead'])], e['win'], e['n'])


@unittest.skipUnless(HAVE_SOLVER and DOUBLE_DUMMY, 'SURE_BIN is not set to a built sure_cpp, or DDS is not built')
class Guarantees(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values = x8_claims.Solver(BIN, ('--keep', '--value'))
        cls.cards = x8_claims.Solver(BIN, ('--keep',))

    @classmethod
    def tearDownClass(cls):
        cls.values.close()
        cls.cards.close()

    def guaranteed(self, text):
        answer = self.values.ask([text], allowance=60., each=60.)[0]
        self.assertIsNotNone(answer, text)
        return answer['value']

    def leads(self, text, need, hand):
        """{card of `hand`: does leading it guarantee `need` tricks}; the solver answers for one card of a run."""
        answer = self.cards.ask(['N%d %s' % (need, text)], allowance=60., each=60.)[0]
        self.assertIsNotNone(answer, text)
        return {x: bool(v) for x, v in answer['cards'].items() if x in hand}

    def test_as_drawn_never_more_than_double_dummy_and_five_in_full(self):
        found = []
        for e in DATA['endings']:
            told, hands, trump = position(e)
            blind, _, _ = position(e, told=False)
            dd = max(double_dummy(hands, trump).values())
            a, b = self.guaranteed(blind), self.guaranteed(told)
            self.assertLessEqual(a, b, e['n'])                      # knowing more never guarantees less
            self.assertLessEqual(b, dd, e['n'])                     # and never more than the cards allow
            self.assertEqual((a, b), (e['guaranteed_nothing_known'], e['guaranteed_every_show_out']), e['n'])
            if e['layouts_left'] == 1:
                self.assertEqual(b, dd, e['n'])                     # every card known: the guarantee is double dummy's
            if b == e['win']:
                found.append(e['n'])
        self.assertEqual(found, FOUND_AS_DRAWN)

    def test_every_marked_version_is_found_and_every_lead_rated_as_double_dummy(self):
        seen = techniques = 0
        for e in DATA['endings']:
            techniques += bool(e['marked'])
            for m in e['marked']:
                for rename in ((0, 1, 2, 3),) + RENAMES:
                    text, hands, trump = position(e, m['west'], m['east'], rename)
                    dd = double_dummy(hands, trump)
                    self.assertEqual(max(dd.values()), e['win'], (e['n'], rename))
                    self.assertEqual(self.guaranteed(text), e['win'], (e['n'], rename))
                    rated = self.leads(text, e['win'], hands[S])
                    self.assertTrue(rated, (e['n'], rename))
                    for x, sure in rated.items():
                        self.assertEqual(sure, dd[x] >= e['win'], (e['n'], rename, x))
                    seen += 1
        self.assertEqual((seen, techniques), (100, 20))

    def test_the_suits_can_be_renamed(self):
        for e in DATA['endings']:
            for told in (False, True):
                want = e['guaranteed_every_show_out' if told else 'guaranteed_nothing_known']
                for rename in RENAMES:
                    text, _, _ = position(e, rename=rename, told=told)
                    self.assertEqual(self.guaranteed(text), want, (e['n'], rename, told))


if __name__ == '__main__':
    unittest.main()
