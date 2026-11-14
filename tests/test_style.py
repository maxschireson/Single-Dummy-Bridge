"""Styles of card play (bridge_harness/style.py) and their two hooks: a search bot's choice among the cards within
`near_tie` of its best, and a rollout bot's choice among its near-equal candidates."""
import random
import unittest

import numpy as np

from bridge_harness import style
from bridge_harness.core import Contract, Observation, card, symbol, winner
from bridge_harness.gen7 import gen7_settings, resolved as gen7_resolved
from bridge_harness.x8_player import resolved, x8_settings
from test_gen7 import Fixture, played
from test_x8 import Fixture8


def view(hand, trick=(), history=(), actor=1, declarer=0, strain='S', dummy_hand=None):
    """A defender's (or declarer's) view with only what the features read."""
    known = [None] * 4
    known[actor] = tuple(card(x) for x in hand)
    if dummy_hand is not None:
        known[(declarer + 2) % 4] = tuple(card(x) for x in dummy_hand)
    return Observation(controller=actor, actor=actor, known_hands=tuple(known), legal=known[actor],
                       history=tuple((s, card(x)) for s, x in history) + tuple((s, card(x)) for s, x in trick),
                       trick=tuple((s, card(x)) for s, x in trick), leader=trick[0][0] if trick else actor,
                       contract=Contract(3, strain, declarer), dealer=0, vulnerability='None', auction=(), declarer_tricks=0)


class FeatureTests(unittest.TestCase):
    def test_tempo_is_taking_the_trick_now(self):
        o = view(['HA', 'H3', 'D2'], trick=[(0, 'HK')], strain='N')
        self.assertEqual([style.features(o, card(x))['tempo'] for x in ('HA', 'H3')], [1., 0.])
        partner_wins = view(['HA', 'H3'], trick=[(3, 'HK'), (0, 'H2')], strain='N')      # seat 3 is seat 1's partner
        self.assertEqual(style.features(partner_wins, card('HA'))['tempo'], 0.)
        ruff = view(['S2', 'D3'], trick=[(0, 'HK')], strain='S')
        self.assertEqual([style.features(ruff, card(x))['tempo'] for x in ('S2', 'D3')], [1., 0.])

    def test_tempo_on_lead_is_cashing_a_winner(self):
        o = view(['HA', 'HK', 'H3', 'DK'], strain='N')
        self.assertEqual([style.features(o, card(x))['tempo'] for x in ('HA', 'HK', 'H3', 'DK')], [1., 1., 0., 0.])
        after = view(['DK', 'D2'], history=[(0, 'DA'), (1, 'D5'), (2, 'D3'), (3, 'D4')], strain='N')
        self.assertEqual(style.features(after, card('DK'))['tempo'], 1.)             # the ace is gone

    def test_active_is_a_new_suit_or_a_lead_from_under_an_honour(self):
        opening = view(['HK', 'H7', 'H2', 'DQ', 'DJ', 'D3', 'C6', 'C5'], strain='N')
        want = {'H2': 1., 'H7': 1., 'HK': 0., 'D3': 1., 'DQ': 0., 'C6': 0.}       # QJx is broken at the jack (no ten): low from it counts
        self.assertEqual({x: style.features(opening, card(x))['active'] for x in want}, want)
        solid = view(['DK', 'DQ', 'DJ', 'DT', 'D3'], strain='N')
        self.assertEqual(style.features(solid, card('D3'))['active'], 0.)
        later = view(['C6', 'C5', 'S4'], history=[(1, 'C2'), (2, 'C3'), (3, 'C9'), (0, 'CA')], strain='N')
        self.assertEqual([style.features(later, card(x))['active'] for x in ('C6', 'S4')], [0., 1.])   # clubs were this side's lead before

    def test_features_hold_on_random_positions(self):
        seen = 0
        for seed in range(12):
            _, game, before = played(seed, 30)
            for o, _ in before:
                for x in o.legal:
                    f = style.features(o, x)
                    self.assertEqual(f['high'], (x % 13) / 12)
                    if o.trick and f['tempo']:
                        self.assertEqual(winner(list(o.trick) + [(o.actor, x)], o.contract.trump), o.actor)
                    if o.trick:
                        self.assertEqual(f['active'], 0.)
                    seen += 1
        self.assertGreater(seen, 500)

    def test_choose_keeps_the_best_scoring_cards_or_all_of_them(self):
        o = view(['HA', 'H3', 'D2'], trick=[(0, 'HK')], strain='N')
        cards = [card(x) for x in ('HA', 'H3')]
        self.assertEqual(style.choose(o, cards, dict(tempo=1.), .5), [card('HA')])
        self.assertEqual(style.choose(o, cards, dict(tempo=-1.), .5), [card('H3')])
        self.assertEqual(style.choose(o, cards, dict(tempo=1., random=.2), .1), cards)       # the random share: any of them
        self.assertEqual(style.choose(o, cards, dict(tempo=1., random=.2), .3), [card('HA')])
        self.assertEqual(style.choose(o, cards, {}, .5), cards)
        for bad in (dict(speed=1.), dict(tempo=9.), dict(random=2.), dict(tempo=True), [1]):
            with self.assertRaises(ValueError):
                style.check(bad)


class HookTests(Fixture8):
    def test_settings_are_pinned_only_where_set(self):
        self.assertNotIn('style', gen7_resolved(None))
        self.assertEqual(gen7_resolved(dict(style=dict(tempo=1.)))['style'], dict(tempo=1.))
        self.assertNotIn('style', resolved(None)['mix'])
        self.assertEqual(resolved(dict(mix=dict(style=dict(high=-1., random=.1))))['mix']['style'], dict(high=-1., random=.1))
        with self.assertRaises(ValueError):
            gen7_settings(dict(style=dict(nonsense=1.)))
        with self.assertRaises(ValueError):
            x8_settings(dict(mix=dict(style=dict(tempo=5.))))

    def test_a_search_bot_with_a_style_plays_the_card_its_style_prefers_among_its_near_ties(self):
        """With every legal card within the margin, a `high` player plays its highest legal card and a low player its
        lowest; a bot with no style is unchanged by the code."""
        high, low, plain = (self.make(gen7=dict(style=s)) for s in (dict(high=1.), dict(high=-1.), {}))
        for p in (high, low, plain):
            p.near_tie = 99.
        moved = 0
        for seed in range(4):
            _, game, before = played(seed, 20)
            for o, _ in before[4:]:
                if len(o.legal) < 2 or len({x % 13 for x in o.legal}) < 2:
                    continue
                got = {name: p.choose(o, random.Random(seed)).card for name, p in (('high', high), ('low', low), ('plain', plain))}
                self.assertEqual(got['high'] % 13, max(x % 13 for x in o.legal))
                self.assertEqual(got['low'] % 13, min(x % 13 for x in o.legal))
                moved += got['high'] != got['plain']
        self.assertGreater(moved, 0)

    def test_a_search_bot_plays_any_near_tie_for_the_random_share_of_its_decisions(self):
        """With a random share of 1 and every legal card within the margin, the card is one of the legal cards at random:
        over many draws more than one of them is played, whatever the style says."""
        p = self.make(gen7=dict(style=dict(high=1., random=1.)))
        p.near_tie = 99.
        _, game, before = played(1, 20)
        o = next(o for o, _ in before[4:] if len({x % 13 for x in o.legal}) > 2)
        got = {p.choose(o, random.Random(seed)).card for seed in range(40)}
        self.assertTrue(got <= set(o.legal))
        self.assertGreater(len(got), 1)

    def test_a_rollout_bot_with_a_style_keeps_the_candidates_its_style_prefers(self):
        """With every candidate within the margin, a `high` rollout bot plays from the candidate with the highest card and
        a low one from the candidate with the lowest."""
        stages = [dict(mode='rollout', from_trick=1, to_trick=13, layouts=8, first=8, cards=4, prior=0., race=0., seat='top')]
        mix = dict(declarer=True, defender=True, near=13.)
        bots = {k: self.make8(x8=dict(stages=stages, mix=dict(mix, style=dict(high=k))), gen7=dict(search_from_trick=14)) for k in (1., -1.)}
        seen = 0
        for seed in range(4):
            _, game, before = played(seed, 20)
            for o, _ in before[5:]:
                if len(o.legal) < 2 or o.known_hands[o.contract.dummy] is None:
                    continue
                for k, p in bots.items():
                    d = p.choose(o, random.Random(seed))
                    note = d.details.get('x8') or {}
                    if note.get('mode') != 'rollout' or 'styled' not in note:
                        continue
                    ranks = [card(x) % 13 for x in note['styled']]
                    want = max(ranks) if k > 0 else min(ranks)
                    runs = [run for rep, run in zip(note['cards'], note['runs']) if rep in note['styled'] and card(rep) % 13 == want]
                    self.assertIn(symbol(d.card), [x for run in runs for x in run])
                    seen += 1
        self.assertGreater(seen, 6)


if __name__ == '__main__':
    unittest.main()
