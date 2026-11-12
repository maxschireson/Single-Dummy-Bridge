"""Gen 8 prototype: tables whose two sides have declared systems (spec keys table_systems, system_scorer,
lead_systems), and auctions bid beforehand (scripts/gen8_match.py --book)."""
import gzip
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np

from bridge_harness import system_fit as F
from bridge_harness.gen6 import View
from bridge_harness.gen6_nets import FitScorer, LeadNet, hand_types
from bridge_harness.gen7 import Gen7Player
from bridge_harness.system_nets import BoundFitScorer
from test_gen6 import FakeBelief, FakeState
from test_gen7 import Fixture, played

ROOT = Path(__file__).resolve().parents[1]


def match_module():
    spec = importlib.util.spec_from_file_location('gen8_match', ROOT / 'scripts' / 'gen8_match.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TableSystemsTests(Fixture):
    def player(self, **extra):
        spec = dict(id='8-test', engine='gen7', samples=8, near_tie=0., exploration=0., scorer='scorer.npz', lead_belief='lead.npz',
                    lead_state_bidder='bidder.keras', belief='belief.npz', belief_kind='public', gen6={}, gen7_policy='gen7.npz', gen7={}, **extra)
        with patch('bridge_harness.gen6.BidderState', FakeState), patch('bridge_harness.mixed_arena.Weights', FakeBelief):
            p = Gen7Player(spec, self.root)
        self.players.append(p)
        return p

    def system_file(self):
        """The fixture's scorer with one more system, 'toy', whose calls read differently."""
        model = F.Model.load(self.root / 'scorer.npz')
        model.add_system('toy')
        model.p['Wa'][1] = np.random.default_rng(5).standard_normal(model.p['Wa'][1].shape).astype(np.float32) * 0.3
        model.save(self.root / 'sys.npz')
        return 'sys.npz'

    def scores(self, p, o, seat):
        rng = np.random.default_rng(seat)
        member = np.zeros((6, 52), np.int8)
        for row in member:
            row[rng.permutation(52)[:13]] = 1
        length, hon = hand_types(member)
        return p.scorer.type_log_score(length, hon, seat, o.dealer, o.vulnerability, o.auction)

    def test_a_spec_without_these_keys_is_gen7(self):
        p = self.player()
        self.assertIs(type(p.scorer), FitScorer)
        self.assertTrue(p.lead_fits)

    def test_each_side_is_read_by_its_declared_system(self):
        plain, file = self.player(), self.system_file()
        undeclared = self.player(system_scorer=file)
        strangers = self.player(system_scorer=file, table_systems=['never-seen', None])
        toy_ns = self.player(system_scorer=file, table_systems=['toy', None])
        self.assertIsInstance(toy_ns.scorer, BoundFitScorer)
        self.assertIs(toy_ns.net.shown.scorer, toy_ns.scorer)              # the policy net's reading of the auction follows
        differs = {0: 0, 1: 0}
        for seed in range(6):
            board, game, before = played(seed, 1)
            o = game.observation()
            for seat in range(4):
                base = self.scores(plain, o, seat)
                np.testing.assert_allclose(self.scores(undeclared, o, seat), base, rtol=1e-5, atol=1e-5)
                np.testing.assert_allclose(self.scores(strangers, o, seat), base, rtol=1e-5, atol=1e-5)
                differs[seat % 2] += not np.allclose(self.scores(toy_ns, o, seat), base, atol=1e-4)
        self.assertGreater(differs[0], 8)       # North-South's own calls are read by 'toy'
        self.assertGreater(differs[1], 8)       # and so are those calls when East-West's hands are scored

    def test_the_lead_net_serves_only_the_systems_it_was_trained_on(self):
        home = self.player(lead_systems=['house'], table_systems=['house', 'house'])
        away = self.player(lead_systems=['house'], table_systems=['toy', 'house'])
        self.assertTrue(home.lead_fits)
        self.assertFalse(away.lead_fits)
        checked = 0
        for seed in range(12):
            board, game, before = played(seed, 0)
            o = game.observation()
            if not LeadNet.fits(o.auction):
                continue
            self.assertEqual(home.source(o, View(o)), 'lead_net')
            self.assertEqual(away.source(o, View(o)), 'scorer')
            checked += 1
        self.assertGreater(checked, 3)


class AuctionBookTests(Fixture):
    def test_a_booked_auction_is_played_as_written(self):
        g = match_module()
        boards = [g.deal(91, i) for i in range(3)]
        auctions = [['1N', 'PASS', 'PASS', 'PASS'], ['PASS'] * 4, ['1S', 'PASS', '4S', 'PASS', 'PASS', 'PASS']]
        path = self.root / 'book.json.gz'
        with gzip.open(path, 'wt') as f:
            json.dump(dict(seed=91, first=0, tables=[['toy', 'house'], ['house', 'toy']], keys=[b.id for b in boards],
                           table_of=[0, 1, 0], auctions=auctions), f)
        seed, book = g.load_book(path)
        self.assertEqual(seed, 91)
        for i, board in enumerate(boards):
            key, systems, calls = book[i]
            self.assertEqual(key, board.id)
            g.STATE['booked'] = (systems, calls)
            try:
                bid, decisions = g.auction_any(board, [None] * 4)
            finally:
                g.STATE['booked'] = None
            self.assertEqual(list(bid.auction), auctions[i])
            self.assertEqual(bid.auction_source, 'g8:' + '|'.join(systems))
            self.assertEqual([d['seat'] for d in decisions], [(board.dealer + k) % 4 for k in range(len(calls))])
            if i == 1:
                self.assertIsNone(bid.contract)
            else:
                self.assertEqual(bid.contract.level, 1 if i == 0 else 4)


if __name__ == '__main__':
    import unittest
    unittest.main()
