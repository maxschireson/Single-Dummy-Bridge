"""Gen 9 signals (G9-S2): the signal model, carding bots and the signal reader."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from bridge_harness.core import Contract, card
from bridge_harness.corpus import generate
from bridge_harness.gen6 import View
from bridge_harness.gen7 import Gen7Player, hidden_plays
from bridge_harness.gen9 import Gen9Player
from bridge_harness.gen9_play import SignalConfig, carding_parts
from bridge_harness.players import GreedyPlayer
from bridge_harness.runner import play_table
from bridge_harness.signals import SPOT_MASK, SUIT_MASK, SignalModel, lead_table, situation
from test_gen6 import FakeBelief, FakeState
from test_gen7 import Fixture, played

ROOT = Path(__file__).resolve().parents[1]
STANDARD = dict(length_lead_vs_suit='4th', length_lead_vs_nt='4th', lead_from_ak='ace', honor_sequence_lead='top',
                attitude='standard', count='standard', signal_on_partner_lead='attitude', signal_on_declarer_lead='count',
                first_discard='attitude', trump_signal='none')
KINDS = (('partner_lead', 'attitude'), ('declarer_lead', 'count'), ('first_discard', 'odd_even'), ('partner_lead', 'suit_preference'),
         ('first_discard', 'lavinthal'), ('trump', 'count'), ('first_discard', 'count'), ('partner_lead', 'none'))


def random_class(rng, lead=False):
    """(suit, K [1, 52], original [1, 52]): a random thirteen-card hand holding two or more cards of the class."""
    while True:
        suit = int(rng.integers(4))
        orig = np.zeros((1, 52), bool)
        orig[0, rng.permutation(52)[:13]] = True
        K = orig & (SUIT_MASK if lead else SPOT_MASK)[suit][None, :]
        if K.sum() >= 2:
            return suit, K, orig


class SignalModelTests(unittest.TestCase):
    def test_probabilities_over_a_class_sum_to_one_in_every_layout(self):
        rng = np.random.default_rng(1)
        for h in (0., .3, .8, 1.):
            for eps in (0., .05):
                m = SignalModel(dict(STANDARD, attitude='upside_down', first_discard='odd_even'), h, eps)
                for key, kind in KINDS + (('lead.opening', 'lead'),):
                    for _ in range(30):
                        suit, K, orig = random_class(rng, lead=kind == 'lead')
                        trump = int(rng.integers(5))
                        # four layouts: the same class, different other cards (so different facts)
                        Ks, origs = np.repeat(K, 4, axis=0), np.repeat(orig, 4, axis=0)
                        for j in range(1, 4):
                            free = np.flatnonzero(~origs[j] & ~SUIT_MASK[suit])
                            mine = np.flatnonzero(origs[j] & ~SUIT_MASK[suit])
                            k = min(len(mine), j)
                            origs[j, mine[:k]] = False
                            origs[j, rng.choice(free, k, replace=False)] = True
                        total = sum(m.probabilities(key, kind, c, Ks, origs, suit, trump, (suit + 1) % 4, trump == 4)
                                    for c in np.flatnonzero(K[0]))
                        self.assertTrue(np.allclose(total, 1., atol=1e-12), (key, kind, h, eps, total))

    def test_honesty_zero_says_nothing_about_the_fact(self):
        rng = np.random.default_rng(2)
        m = SignalModel(dict(STANDARD, first_discard='odd_even'), 0., .05)
        for key, kind in KINDS:
            for _ in range(30):
                suit, K, orig = random_class(rng)
                Ks, origs = np.repeat(K, 2, axis=0), np.repeat(orig, 2, axis=0)
                origs[1, (suit * 13 + 12)] = not origs[0, suit * 13 + 12]           # an ace in or out of the suit
                side = np.flatnonzero(origs[1] & ~SUIT_MASK[suit])
                if len(side):
                    origs[1, side[0]] = False                                       # a different side-suit holding
                for c in np.flatnonzero(K[0]):
                    p = m.probabilities(key, kind, c, Ks, origs, suit, 1, (suit + 1) % 4)
                    self.assertAlmostEqual(float(p[0]), float(p[1]), places=12)

    def test_honesty_one_plays_the_prescribed_spot(self):
        H = lambda *xs: [card('H' + x) for x in xs]
        m = SignalModel(STANDARD, 1., 0.)
        self.assertEqual(m.distribution('partner_lead', 'attitude', H('7', '4', '2'), H('A', '7', '4', '2'), 1, 0, 1)[card('H7')], 1.)
        self.assertEqual(m.distribution('partner_lead', 'attitude', H('7', '4', '2'), H('J', '7', '4', '2'), 1, 0, 1)[card('H2')], 1.)
        self.assertEqual(m.distribution('declarer_lead', 'count', H('7', '4', '2'), H('7', '4', '2'), 1, 0, 2)[card('H2')], 1.)
        self.assertEqual(m.distribution('declarer_lead', 'count', H('7', '2'), H('7', '2'), 1, 0, 2)[card('H7')], 1.)
        ud = SignalModel(dict(STANDARD, count='upside_down', attitude='upside_down'), 1., 0.)
        self.assertEqual(ud.distribution('declarer_lead', 'count', H('7', '4', '2'), H('7', '4', '2'), 1, 0, 2)[card('H7')], 1.)
        self.assertEqual(ud.distribution('partner_lead', 'attitude', H('7', '4', '2'), H('A', '7', '4', '2'), 1, 0, 1)[card('H2')], 1.)
        oe = SignalModel(dict(STANDARD, first_discard='odd_even'), 1., 0.)
        self.assertEqual(oe.distribution('first_discard', 'odd_even', H('8', '7', '4', '3'), H('K', '8', '7', '4', '3'), 1, 0, 2)[card('H7')], 1.)
        self.assertEqual(oe.distribution('first_discard', 'odd_even', H('8', '7', '4', '3'), H('8', '7', '4', '3'), 1, 0, 2)[card('H4')], 1.)
        sp = [card(x) for x in ('SA', 'SK', 'C2', 'H7', 'H2')]                     # spades stronger than clubs: high spot
        self.assertEqual(m.distribution('partner_lead', 'suit_preference', H('7', '2'), sp, 1, 2, 1)[card('H7')], 1.)
        half = SignalModel(STANDARD, .5, 0.)                                       # message form: noise is half high, half low
        self.assertEqual(half.distribution('partner_lead', 'attitude', H('7', '4', '2'), H('A', '7', '4', '2'), 1, 0, 1),
                         {card('H2'): .25, card('H4'): 0., card('H7'): .75})
        self.assertEqual(m.distribution('lead.opening', 'lead', H('K', 'J', '7', '5', '3'), H('K', 'J', '7', '5', '3'), 1, 0, 1)[card('H5')], 1.)

    def test_emission_tables(self):
        rng = np.random.default_rng(5)
        h = .7
        symmetric = [[(1 - h) / 2, h + (1 - h) / 2, 0.], [h + (1 - h) / 2, (1 - h) / 2, 0.]]       # count: even -> high
        ben_like = [[.70, .22, .08], [.88, .05, .07]]
        flat = [[.6, .3, .1], [.6, .3, .1]]
        honest = SignalModel(STANDARD, h, .05)
        for table, check in ((symmetric, 'honesty'), (ben_like, 'sum'), (flat, 'flat')):
            m = SignalModel(STANDARD, h, .05, emission={'declarer_lead.count': table})
            for _ in range(60):
                suit, K, orig = random_class(rng)
                cs = np.flatnonzero(K[0])
                p = np.array([m.probabilities('declarer_lead', 'count', c, K, orig, suit, 1, suit)[0] for c in cs])
                self.assertAlmostEqual(p.sum(), 1., places=12)
                if check == 'honesty':
                    q = np.array([honest.probabilities('declarer_lead', 'count', c, K, orig, suit, 1, suit)[0] for c in cs])
                    self.assertTrue(np.allclose(p, q))
                if check == 'flat':                                          # equal rows: the card says nothing about the fact
                    other = orig.copy()
                    extra = [c for c in range(52) if c // 13 != suit and not other[0, c]][0]
                    other[0, extra] = True                                   # one more card elsewhere: the suit's parity is unchanged
                    flip = orig.copy()
                    flip[0, [c for c in range(suit * 13 + 8, suit * 13 + 13) if not K[0, c]][:1]] ^= True   # an honour in or out: parity flips
                    q = np.array([m.probabilities('declarer_lead', 'count', c, K, flip, suit, 1, suit)[0] for c in cs])
                    self.assertTrue(np.allclose(p, q))
        with self.assertRaises(ValueError):
            SignalModel(STANDARD, emission={'declarer_lead.count': [[.5, .5]]})

    def test_lead_conventions(self):
        def lead(holding, *args):
            return '23456789TJQKA'[lead_table(*args)[sum(1 << '23456789TJQKA'.index(r) for r in holding)]]
        cases = {('4th', 'ace', 'top'): {'KQ5': 'K', 'AK63': 'A', 'KJ753': '5', 'Q83': '3', 'J9742': '4', 'T98': 'T', 'AQ5': '5',
                                         'K': 'K', '852': '8', '96': '9', '7532': '2'},
                 ('3rd_5th', 'king', 'rusinow'): {'KQ5': 'Q', 'AK63': 'K', 'KJ753': '3', 'K8642': '2', 'Q873': '7', 'QJ5': 'J'},
                 ('attitude', 'ace', 'top'): {'K8642': '2', '98642': '9', 'J752': '2'}}
        cases[('4th', 'ace', 'top', 'low', 'second')] = {'852': '2', '7532': '5', '98642': '8', 'KJ753': '5', 'Q83': '3', 'KQ5': 'K'}
        cases[('4th', 'ace', 'top', 'middle', '4th')] = {'852': '5', '7532': '2'}          # MUD from three small
        for args, expected in cases.items():
            for holding, want in expected.items():
                self.assertEqual(lead(holding, *args), want, (args, holding))

    def test_situations_from_public_play(self):
        contract = Contract(4, 'H', 0)                      # North declares four hearts; East leads
        E, S, W, N = 1, 2, 3, 0
        h = [(E, card('SK')), (S, card('S3')), (W, card('S7')), (N, card('SA')),     # 1: West follows to partner's lead
             (N, card('D2')), (E, card('D9')), (S, card('DK')), (W, card('C4')),     # 2: East follows to declarer; West's first discard
             (S, card('S4')), (W, card('S2')), (N, card('S5')), (E, card('SQ')),     # 3: second round of spades
             (E, card('D3')), (S, card('DA')), (W, card('C2')), (N, card('D4')),     # 4: West's second discard
             (N, card('H2')), (E, card('H5')), (S, card('H9')), (W, card('S6'))]     # 5: trumps
        got = [situation(h, i, contract) for i in range(len(h))]
        self.assertEqual(got[0], ('lead.opening', 0))
        self.assertEqual(got[2], ('partner_lead', 0))
        self.assertEqual(got[5], ('declarer_lead', 2))
        self.assertEqual(got[7], ('first_discard', 3))
        self.assertEqual(got[17], ('trump', 1))
        for i in (1, 3, 4, 6, 8, 9, 10, 11, 12, 14, 16, 19):                       # declarer, dummy, later leads and rounds, later discards
            self.assertIsNone(got[i], i)


class Gen9Fixture(Fixture):
    def make_gen9(self, gen9, gen7=None, **switches):
        spec = dict(id='9-test', engine='gen9', samples=8, near_tie=0., exploration=0., scorer='scorer.npz', lead_belief='lead.npz',
                    lead_state_bidder='bidder.keras', belief='belief.npz', belief_kind='public', gen6=switches,
                    gen7_policy='gen7.npz', gen7=gen7 or {}, gen9=gen9)
        with patch('bridge_harness.gen6.BidderState', FakeState), patch('bridge_harness.mixed_arena.Weights', FakeBelief):
            p = Gen9Player(spec, self.root)
        self.players.append(p)
        return p


def defending(board):
    """Seat assignments with the carding bot ('c') defending and the greedy player declaring."""
    d = board.contract.declarer
    return ['g' if s % 2 == d % 2 else 'c' for s in range(4)]


class CardingBotTests(Gen9Fixture):
    def bot(self, honesty):
        return self.make_gen9(dict(carding=dict(descriptor=STANDARD, honesty=honesty)), gen7=dict(play_weight=0.))

    def signalled(self, p, seeds):
        out = []
        for seed in seeds:
            board = next(generate(1, 1200 + seed))
            result = play_table(board, defending(board), {'c': p, 'g': GreedyPlayer()}, seed=seed)
            self.assertEqual(result['status'], 'ok', result.get('traceback'))
            out += [(board, a) for a in result['actions'] if str(a.get('selector', '')).startswith('carding-')]
        return out

    def test_honest_bot_plays_the_prescribed_card_among_its_ties(self):
        seen = {}
        for board, a in self.signalled(self.bot(1.), range(8)):
            x = card(a['card'])
            tied = {card(k) for k, q in a['proposal_probabilities'].items() if q > 0}
            self.assertIn(x, tied)
            s = a['gen9_signal']
            seen[s['kind']] = seen.get(s['kind'], 0) + 1
            if s['kind'] == 'none':                                             # no signal applies (later rounds): uniform in the class
                self.assertEqual(sorted(set(q for q in a['behavior_probabilities'].values() if q > 0)), [1 / s['choices']])
                continue
            self.assertEqual(a['selected_probability'], 1.)
            hand = set(board.hands['NESW'.index(a['seat'])])
            suit = x // 13
            choices = sorted(y for y in tied if y // 13 == suit and y % 13 <= 7)
            if s['kind'] == 'attitude':                                         # standard: high with the A, K or Q
                like = any(y // 13 == suit and y % 13 >= 10 for y in hand)
                self.assertEqual(x, choices[-1] if like else choices[0])
            if s['kind'] == 'count':                                            # standard: high from an even number
                even = sum(1 for y in hand if y // 13 == suit) % 2 == 0
                self.assertEqual(x, choices[-1] if even else choices[0])
        self.assertGreater(sum(seen.values()) - seen.get('none', 0), 10, seen)
        self.assertTrue({'attitude', 'count', 'lead', 'none'} <= set(seen), seen)

    def test_dishonest_bot_spreads_its_spots_by_message_alone(self):
        checked = 0
        for board, a in self.signalled(self.bot(0.), range(8)):
            if a['gen9_signal']['kind'] in ('attitude', 'count') and a['gen9_signal']['choices'] == 2:
                self.assertEqual(sorted(q for q in a['behavior_probabilities'].values() if q > 0), [.5, .5])
                checked += 1
        self.assertGreater(checked, 3)

    def test_no_gen9_settings_is_the_gen7_player_card_for_card(self):
        plain = self.make_gen9({}, gen7=dict(play_weight=0.))
        base = self.make(Gen7Player, gen7=dict(play_weight=0.))
        for seed in range(3):
            board = next(generate(1, 1300 + seed))
            a = play_table(board, defending(board), {'c': plain, 'g': GreedyPlayer()}, seed=seed)
            b = play_table(board, defending(board), {'c': base, 'g': GreedyPlayer()}, seed=seed)
            self.assertEqual([x['card'] for x in a['actions']], [x['card'] for x in b['actions']])


class ReaderTests(Gen9Fixture):
    GEN7 = dict(early_play_weight=1., opponent_play_weight={'*': .5})

    def positions(self, seeds, plies, declaring=None):
        for seed in seeds:
            for n in plies:
                board, game, before = played(seed, n)
                o = game.observation()
                if len(View(o).hidden) != 2 or len(o.legal) < 2:
                    continue
                if declaring is not None and (o.controller % 2 == o.contract.declarer % 2) != declaring:
                    continue
                yield o, View(o)

    def test_plain_or_uncarded_opponents_are_read_exactly_as_gen8(self):
        base = self.make(Gen7Player, gen7=self.GEN7)
        others = [self.make_gen9({}, gen7=self.GEN7),
                  self.make_gen9(dict(models={'x': dict(kind='synthetic')}), gen7=self.GEN7),
                  self.make_gen9(dict(models={'y': dict(kind='synthetic', carding=dict(descriptor=STANDARD))}), gen7=self.GEN7)]
        for p in [base] + others:
            p.meet('x')
        n = 0
        for o, v in self.positions(range(30), (6, 10, 15)):
            assign = v.uniform(16, np.random.default_rng(n))
            want = base.play_log_likelihood(o, v, assign)
            for p in others:
                net, signal = p.play_log_terms(o, v, assign)
                self.assertTrue(np.array_equal(net, want))
                self.assertFalse(signal.any())
                self.assertTrue(np.array_equal(p.play_log_likelihood(o, v, assign), want))
            n += 1
        self.assertGreater(n, 10)

    def test_declared_carding_splits_class_and_spot(self):
        base = self.make(Gen7Player, gen7=self.GEN7)
        reader = self.make_gen9(dict(models={'x': dict(kind='synthetic', carding=dict(descriptor=STANDARD, honesty=.8))}), gen7=self.GEN7)
        silent = self.make_gen9(dict(models={'x': dict(kind='synthetic', carding=dict(descriptor=dict(attitude='standard'), honesty=.8))}),
                                gen7=self.GEN7)                             # a descriptor naming no situation: nothing to read
        for p in (base, reader, silent):
            p.meet('x')
        self.assertEqual(reader.opponent_phi, .5)
        spots = honours = moved = 0
        for o, v in self.positions(range(80), (3, 6, 9, 13), declaring=True):
            assign = v.uniform(24, np.random.default_rng(spots + honours))
            for play in hidden_plays(o):
                i = play[0]
                x = o.history[i][1]
                sit = situation(o.history, i, o.contract)
                g8 = base.play_log_likelihood(o, v, assign, [play])
                net, signal = reader.play_log_terms(o, v, assign, [play])
                self.assertTrue(np.array_equal(silent.play_log_likelihood(o, v, assign, [play]), g8))
                card_term, _, _ = reader.signal_row(o, v, assign, *play, reader.opponent_signals)
                self.assertTrue(np.allclose(reader.opponent_phi * card_term, g8))     # the card term is Gen 8's, for spots too
                lead = sit is not None and sit[0] == 'lead.opening'
                if x % 13 > 7 and not lead:
                    self.assertTrue(np.allclose(net, g8))                   # an honour is its own class: Gen 8's term
                    self.assertFalse(signal.any())
                    honours += 1
                    continue
                self.assertTrue((net >= g8 - 1e-9).all())                   # a class is at least as likely as one of its cards
                self.assertTrue((signal <= 1e-12).all())
                spots += 1
                moved += bool(np.abs(net + signal - g8).max() > 1e-6)
        self.assertGreater(spots, 10)
        self.assertGreater(honours, 3)
        self.assertGreater(moved, 5)

    def test_unstated_honesty_is_learned_from_experience(self):
        from bridge_harness import experience as xp
        stats = {'card.partner_lead.attitude': xp.count(**{'hit/2': 90, 'all/2': 100, 'hit/2/3': 90, 'all/2/3': 100}),
                 'card.declarer_lead.count': xp.count(**{'hit/2': 50, 'all/2': 100, 'hit/2/2': 50, 'all/2/2': 100})}
        store = xp.add(xp.empty('x'), xp.delta('x', 'b1', stats))
        learned = dict(kind='guest', carding=dict(descriptor=STANDARD), experience=xp.snapshot(store, 'epoch-1'))
        p = self.make_gen9(dict(models={'x': learned, 'y': dict(kind='guest', carding=dict(descriptor=STANDARD)),
                                        'z': dict(kind='guest', carding=dict(descriptor=STANDARD, honesty=.9), experience=xp.snapshot(store, 'e'))}))
        p.meet('x')
        self.assertGreater(p.opponent_signals.honesty('partner_lead.attitude'), .7)
        self.assertLess(p.opponent_signals.honesty('declarer_lead.count'), .25)                # 100 occasions at chance: a posterior mean near 0
        self.assertTrue(.3 < p.opponent_signals.honesty('first_discard.attitude') < .7)          # unseen key: the pooled value
        p.meet('y')
        self.assertEqual(p.opponent_signals.honesty('partner_lead.attitude'), .5)                 # nothing learned: the low default
        p.meet('z')
        self.assertEqual(p.opponent_signals.honesty('declarer_lead.count'), .9)                   # stated: believed as stated

    def test_emission_tables_stated_or_learned(self):
        from bridge_harness import experience as xp
        table = [[.7, .22, .08], [.88, .05, .07]]
        stated = dict(kind='outside', carding=dict(descriptor=STANDARD, emission={'declarer_lead.count': table}))
        counts = {'m0/low': 140., 'm0/high': 44., 'm0/mid': 16., 'm1/low': 176., 'm1/high': 10., 'm1/mid': 14.}
        store = xp.add(xp.empty('x'), xp.delta('x', 'b', {'card.declarer_lead.count.emit': xp.count(**counts)}))
        learned = dict(kind='outside', carding=dict(descriptor=STANDARD), experience=xp.snapshot(store, 'e1'))
        few = xp.add(xp.empty('y'), xp.delta('y', 'b', {'card.declarer_lead.count.emit': xp.count(**{k: v / 10 for k, v in counts.items()})}))
        p = self.make_gen9(dict(models={'s': stated, 'l': learned, 'f': dict(kind='outside', carding=dict(descriptor=STANDARD),
                                                                          experience=xp.snapshot(few, 'e1'))}))
        p.meet('s')
        self.assertTrue(np.allclose(p.opponent_signals.emission['declarer_lead.count'], table))
        p.meet('l')
        rows = p.opponent_signals.emission['declarer_lead.count']
        self.assertGreater(rows[0][1] / rows[1][1], 2.)                     # a high spot says even, as the counts do
        p.meet('f')
        self.assertEqual(p.opponent_signals.emission, {})                   # 40 occasions: below emission_min, no table yet

    def test_meet_resolves_models_by_id(self):
        models = {'x': dict(kind='synthetic', carding=dict(descriptor=STANDARD, honesty={'*': .9, 'partner_lead.attitude': .6}, phi=.4))}
        p = self.make_gen9(dict(models=models))
        p.meet('x')
        self.assertEqual(p.opponent_phi, .4)
        self.assertEqual(p.opponent_signals.honesty('partner_lead.attitude'), .6)
        self.assertEqual(p.opponent_signals.honesty('declarer_lead.count'), .9)
        p.meet('y')
        self.assertIsNone(p.opponent_signals)
        with self.assertRaises(ValueError):
            SignalConfig(models={'x': dict(carding=dict(descriptor=dict(attitude='sideways')))})
        with self.assertRaises(ValueError):
            SignalConfig(read_partner=True)


class BotEntriesTests(unittest.TestCase):
    def test_signal_bot_entries(self):
        bots = json.loads((ROOT / 'configs' / 'gen9-signal-bots.json').read_text())
        for scheme in ('std', 'ud'):
            for h in ('100', '80', '50'):
                self.assertIn(f'c-{scheme}-{h}', bots)
        for key, entry in bots.items():
            if key.startswith('_'):
                continue
            self.assertEqual(entry['engine'], 'gen9', key)
            config = SignalConfig(**entry['gen9'])
            if key.startswith('c-'):
                descriptor, honesty = carding_parts(config.carding)
                self.assertEqual(float(honesty), int(key.split('-')[-1]) / 100)
                self.assertEqual(descriptor['count'], 'upside_down' if '-ud' in key else 'standard')



class RunBotsTests(unittest.TestCase):
    def test_the_run_file_matches_its_sources(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('run_bots', ROOT / 'scripts' / 'gen9_signal_run_bots.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(json.loads((ROOT / 'configs' / 'gen9-signal-run-bots.json').read_text()), module.merged())
        for bot in ('8p-32', '8x-32', 'r9-32', 'c-std-80', 'cp-std-100', 'cp-att-100', 'r9p-32'):
            self.assertIn(bot, module.merged())


class CardingPackageTests(unittest.TestCase):
    def test_guest_packages(self):
        for gid, h in (('guest-a', .8), ('guest-b', 0.)):
            doc = json.loads((ROOT / 'configs' / 'carding' / f'{gid}.json').read_text())
            self.assertNotIn('honesty', doc['declared'])                       # the declaration states no honesty
            descriptor, _ = carding_parts(doc['declared'])
            self.assertTrue(SignalModel(descriptor))                           # an active declaration: spots and leads are read
            config = SignalConfig(**doc["play"]["gen9"])
            self.assertEqual(carding_parts(config.carding), (descriptor, h))   # the guest plays what it declares, at its honesty
        for name in ('ben16', 'ben64'):                                        # fitted models of an outside player (E9-7)
            doc = json.loads((ROOT / 'configs' / 'carding' / f'{name}.json').read_text())
            block = doc['carding']
            m = SignalModel(carding_parts(block)[0], block['honesty'], .05, emission=block['emission'])
            self.assertEqual(set(m.emission), {'partner_lead.count', 'declarer_lead.count', 'first_discard.count', 'trump.count'})
            even, odd = m.emission['declarer_lead.count']
            self.assertGreater(even[1], 2 * odd[1])                            # BEN's high spot says even


if __name__ == '__main__':
    unittest.main()
