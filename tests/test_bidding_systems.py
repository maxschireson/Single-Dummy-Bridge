"""Systems as data, the system-aware hand-fit scorer, queryable bidders and the trainer.

Every training test uses three or more systems: nothing may depend on there being two.
"""
import json
import math
import os
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from bridge_harness import system_fit as F
from bridge_harness.bidding_env import CALLS, legal_mask
from bridge_harness.core import auction_contract
from bridge_harness.gen6_nets import FitScorer
from bridge_harness.system_bidders import PASS, ToyBidder, VUL_NAMES, _RuleSession, bid, make_bidder, options_sha256
from bridge_harness.system_nets import OWN_ROWS, SystemFitScorer
from bridge_harness.systems import (DescriptorVocabulary, SystemPackage, SystemRegistry, TableSystems, card_descriptor)

ROOT = Path(__file__).resolve().parents[1]
TOYS = {'toy-strong': ToyBidder((15, 17), 5), 'toy-weak': ToyBidder((12, 14), 4), 'toy-club': ToyBidder((13, 15), 5, 16),
        'toy-mini': ToyBidder((10, 12), 5)}
AUCTION = ('PASS', '1H', 'X', '2H', 'PASS', 'PASS', '2S', 'PASS', 'PASS', 'PASS')


def package(sid, **over):
    d = dict(schema='system-package-v1', id=sid, display_name=sid, status='active', bidding={}, carding={},
             generators=[dict(kind='toy', options={}, sha256=format(abs(hash(sid)) % 16 ** 16, '064x'))])
    d.update(over)
    return d


def toy_data(seed, per_table, ids):
    """Every ordered pairing of the toy systems `ids`, per_table deals each."""
    parts = []
    for i, ns in enumerate(ids):
        for j, ew in enumerate(ids):
            q = F.generate(np.random.default_rng([seed, i, j]), (TOYS[ns], TOYS[ew]), per_table, chunk=256)
            names = [ns] if ns == ew else [ns, ew]
            q.update(systems=np.array(names), generators=np.array([TOYS[s].sha256 for s in names]),
                     d_sys=np.tile(np.array([0, len(names) - 1]), (len(q['d_dealer']), 1)))
            parts.append(q)
    return F.merge(parts)


def legacy_weights(path, seed=0, widths=(16, 8, 8)):
    """A scorer file as written before systems existed (tests/test_gen6.py)."""
    r = np.random.default_rng(seed)
    w = lambda a, b: (r.standard_normal((a, b)) / math.sqrt(a)).astype(np.float32)
    w0, w1, w2 = widths
    np.savez(path, Wh=3 * w(120, w0), Wa=w(28 * 38, w0), b0=np.zeros(w0, np.float32), W1=w(w0, w1), b1=np.zeros(w1, np.float32),
             W2=w(w1, w2), b2=np.zeros(w2, np.float32), Wo=3 * w(w2, 1), bo=np.zeros(1, np.float32))


def random_members(n, seed=1):
    r = np.random.default_rng(seed)
    member = np.zeros((n, 52), np.int8)
    for row in member:
        row[r.choice(52, 13, replace=False)] = 1
    return member


class RegistryTests(unittest.TestCase):
    def write(self, folder, *packages, fields=None):
        for p in packages:
            (folder / f'{p["id"]}.json').write_text(json.dumps(p))
        if fields:
            (folder / '_carding_fields.json').write_text(json.dumps(dict(schema='carding-fields-v1', fields=fields)))

    def test_repository_registry_loads_and_pins_its_generators(self):
        registry = SystemRegistry.load()
        self.assertGreaterEqual(len(registry.ids()), 3)
        for sid in registry.ids():
            p = registry[sid]
            self.assertEqual(p.id, sid)
            for g in p.generators:
                if g.get('sha256'):
                    self.assertEqual(registry.system_of_generator(g['sha256']), sid)
                    registry.require_generator(sid, g['sha256'])
                if p.status == 'active' and not g.get('external'):
                    self.assertTrue(g.get('path'), sid)
            parent = p.lineage.get('parent')
            self.assertTrue(parent is None or parent in registry, sid)

    def test_any_number_of_packages(self):
        with tempfile.TemporaryDirectory() as d:
            ids = [f's{i:02d}' for i in range(17)]
            self.write(Path(d), *[package(s) for s in ids])
            self.assertEqual(SystemRegistry.load(d).ids(), tuple(ids))

    def test_invalid_packages_are_refused(self):
        bad = [package('Unknown Id'), package('unknown'), package('a', status='live'), package('a', surprise=1),
               package('a', generators=[dict(kind='toy')]), package('a', generators=[dict(kind='toy', sha256='abc')]),
               package('a', bidding=dict(card='acbl.pdf')), dict(package('a'), schema='other')]
        for d in bad:
            with self.assertRaises(ValueError, msg=str(d)[:80]):
                SystemPackage.from_dict(d)
        SystemPackage.from_dict(package('a', status='draft', generators=[dict(kind='toy')]))      # a draft may be unpinned

    def test_registry_refuses_duplicates_and_shared_generators(self):
        a, b = SystemPackage.from_dict(package('a')), SystemPackage.from_dict(package('b'))
        with self.assertRaises(ValueError):
            SystemRegistry([a, a])
        with self.assertRaises(ValueError):
            SystemRegistry([a, SystemPackage.from_dict(package('b', generators=list(a.generators)))])
        registry = SystemRegistry([a, b])
        with self.assertRaises(ValueError):
            registry.require_generator('b', a.generators[0]['sha256'])
        with self.assertRaises(ValueError):
            registry.check_declared('never-registered')
        registry.check_declared(None)
        registry.check_declared('unknown')

    def test_file_name_and_carding_fields_are_checked(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'other.json').write_text(json.dumps(package('a')))
            with self.assertRaises(ValueError):
                SystemRegistry.load(d)
        with tempfile.TemporaryDirectory() as d:
            fields = dict(count=['standard', 'upside_down'])
            self.write(Path(d), package('a', carding=dict(descriptor=dict(count='upside_down'))), fields=fields)
            self.assertEqual(SystemRegistry.load(d)['a'].carding['descriptor'], dict(count='upside_down'))
            self.write(Path(d), package('b', carding=dict(descriptor=dict(count='sideways'))))
            with self.assertRaises(ValueError):
                SystemRegistry.load(d)


class TableTests(unittest.TestCase):
    def test_sides_and_seats(self):
        t = TableSystems('a', 'b')
        self.assertEqual([t.of(s) for s in range(4)], ['a', 'b', 'a', 'b'])
        self.assertEqual(t.for_seat(2), ('a', 'b'))
        self.assertEqual(t.for_seat(3), ('b', 'a'))
        self.assertEqual(TableSystems('a', 'unknown'), TableSystems('a', None))
        self.assertEqual(TableSystems.from_seats(['a', None, 'a', None]), TableSystems('a'))
        with self.assertRaises(ValueError):
            TableSystems.from_seats(['a', 'b', 'c', 'b'])

    def test_views(self):
        t = TableSystems('a', 'b')
        self.assertEqual(t.view('declared'), t)
        self.assertEqual(t.view('unknown'), TableSystems())
        seen = {t.view('partnership', random.Random(i)) for i in range(64)}
        self.assertEqual(seen, {t, TableSystems('a'), TableSystems(None, 'b'), TableSystems()})
        with self.assertRaises(ValueError):
            t.view('partnership')


class VocabularyTests(unittest.TestCase):
    def test_encoding_keeps_missing_and_unseen_values_representable(self):
        v = DescriptorVocabulary(dict(count=['standard', 'upside_down'], smith=['none', 'standard', 'reverse']))
        self.assertEqual(v.size, 7)
        self.assertEqual(v.encode(dict(count='Upside_Down')).tolist(), [0, 0, 1, 1, 0, 0, 0])
        self.assertEqual(v.encode(dict(count='sideways', smith='none')).tolist(), [1, 0, 0, 0, 1, 0, 0])
        self.assertEqual(v.encode(None).tolist(), [1, 0, 0, 1, 0, 0, 0])
        again = DescriptorVocabulary.from_json(v.to_json())
        self.assertEqual(again.fields, v.fields)

    def test_vocabulary_from_a_population_of_cards(self):
        cards = [{'System type': '0', 'Drury': '1'}, {'System type': '3', 'Drury': 0, 'Multi': True}]
        v = DescriptorVocabulary.from_descriptors(cards)
        self.assertEqual(v.fields, {'Drury': ('0', '1'), 'Multi': ('1',), 'System type': ('0', '3')})
        self.assertEqual(int(v.encode(cards[1]).sum()), 3)

    def test_card_reader(self):
        from bridge_harness import systems
        def lines(text):            # a stand-in format: "name = value" lines
            return dict(line.split(' = ') for line in text.splitlines() if ' = ' in line)
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'card.txt').write_text('Opening one no trump = 15-17\nMajors = five\n')
            with self.assertRaises(ValueError):             # no format has a reader yet
                card_descriptor(dict(format='lines', path='card.txt'), d)
            systems.CARD_READERS['lines'] = lines
            try:
                self.assertEqual(card_descriptor(dict(format='lines', path='card.txt'), d)['Majors'], 'five')
                with self.assertRaises(ValueError):
                    card_descriptor(dict(format='lines'), d)
            finally:
                del systems.CARD_READERS['lines']


class ScorerTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    def test_a_pre_system_file_scores_exactly_as_fitscorer(self):
        legacy_weights(self.root / 's.npz')
        old, new = FitScorer(self.root / 's.npz'), SystemFitScorer(self.root / 's.npz')
        member = random_members(300)
        for seat in range(4):
            for dealer in range(4):
                a = old.seat_log_score(member, seat, dealer, 'NS', AUCTION)
                for systems in (None, TableSystems('x', 'y'), TableSystems(None, 'x')):
                    self.assertTrue(np.array_equal(a, new.seat_log_score(member, seat, dealer, 'NS', AUCTION, systems)))
        self.assertEqual(new.unseen, {'x', 'y'})

    def model(self, systems, seed=0):
        model = F.Model.new(systems, seed=seed, widths=(16, 8, 8))
        r = np.random.default_rng(seed + 1)
        model.p['Wa'][1:] = (r.standard_normal(model.p['Wa'][1:].shape) * 0.5).astype(np.float32)
        return model

    def test_each_slot_uses_the_table_of_the_side_that_called(self):
        model = self.model(['a', 'b', 'c'])
        model.save(self.root / 'm.npz', dict(note='test'))
        scorer = SystemFitScorer(self.root / 'm.npz')
        self.assertEqual(scorer.ids, ('unknown', 'a', 'b', 'c'))
        self.assertIn('test', scorer.meta)
        wa = model.p['Wa']
        table = scorer.table('a', 'c')
        self.assertTrue(np.array_equal(table[OWN_ROWS], (wa[0] + wa[1])[OWN_ROWS]))
        self.assertTrue(np.array_equal(table[~OWN_ROWS], (wa[0] + wa[3])[~OWN_ROWS]))
        self.assertTrue(np.array_equal(scorer.table(None, None), wa[0]))
        bound = scorer.bind(TableSystems('a', 'c'))
        self.assertTrue(np.array_equal(bound.tables[0], scorer.table('a', 'c')))       # a North-South seat
        self.assertTrue(np.array_equal(bound.tables[1], scorer.table('c', 'a')))       # an East-West seat
        member = random_members(64)
        declared = scorer.seat_log_score(member, 1, 0, 'None', AUCTION, TableSystems('a', 'c'))
        self.assertFalse(np.allclose(declared, scorer.seat_log_score(member, 1, 0, 'None', AUCTION, TableSystems('c', 'a'))))

    def test_a_system_the_file_never_saw_reads_as_unknown(self):
        self.model(['a', 'b']).save(self.root / 'm.npz')
        scorer = SystemFitScorer(self.root / 'm.npz')
        member = random_members(64)
        nothing = scorer.seat_log_score(member, 0, 1, 'Both', AUCTION)
        self.assertTrue(np.array_equal(nothing, scorer.seat_log_score(member, 0, 1, 'Both', AUCTION, TableSystems('zz', 'yy'))))
        self.assertEqual(scorer.unseen, {'zz', 'yy'})
        half = scorer.seat_log_score(member, 0, 1, 'Both', AUCTION, TableSystems('a', 'zz'))
        self.assertTrue(np.array_equal(half, scorer.seat_log_score(member, 0, 1, 'Both', AUCTION, TableSystems('a'))))
        self.assertFalse(np.allclose(half, nothing))

    def test_inference_equals_the_trainer_forward(self):
        data = toy_data(3, 40, ['toy-strong', 'toy-weak', 'toy-club'])
        model = self.model([str(s) for s in data['systems']], seed=4)
        model.save(self.root / 'm.npz')
        scorer = SystemFitScorer(self.root / 'm.npz')
        ix = np.random.default_rng(0).choice(len(data['label']), 120, replace=False)
        xh, xa, _, own, opp = F.batch(model, data, ix)
        want = -np.logaddexp(0.0, -F.forward(model.p, xh, F.parts_of(xa, model.gate, own, opp))[0])
        systems = [str(s) for s in data['systems']]
        for n, i in enumerate(ix):
            dl, seat = int(data['deal'][i]), int(data['seat'][i])
            ns, ew = (systems[k] for k in data['d_sys'][dl])
            auction = tuple(CALLS[c] for c in data['d_calls'][dl] if c >= 0)
            got = scorer.type_log_score(data['length'][i][None].astype(np.int64), data['hon'][i][None].astype(np.int64), seat,
                                        int(data['d_dealer'][dl]), VUL_NAMES[data['d_vul'][dl]], auction, TableSystems(ns, ew))
            self.assertAlmostEqual(float(got[0]), float(want[n]), places=4)

    def test_malformed_files_are_refused(self):
        model = self.model(['a'])
        np.savez(self.root / 'bad.npz', **model.p, sys_ids=np.array(['a', 'unknown']), sys_gate=model.gate)
        with self.assertRaises(ValueError):
            SystemFitScorer(self.root / 'bad.npz')
        np.savez(self.root / 'bad2.npz', **model.p, sys_ids=np.array(['unknown', 'a', 'b']), sys_gate=model.gate)
        with self.assertRaises(ValueError):
            SystemFitScorer(self.root / 'bad2.npz')


class BidderTests(unittest.TestCase):
    def test_mixed_table_auctions_are_legal_complete_and_follow_each_sides_agreements(self):
        rng = np.random.default_rng(0)
        hands, dealer, vul = F.deal(rng, 600)
        sim = F.simulate((TOYS['toy-weak'], TOYS['toy-club']), hands, dealer, vul)
        for b in range(120):
            calls = [CALLS[c] for c in sim['calls'][b] if c >= 0]
            for i in range(len(calls)):
                self.assertTrue(np.array_equal(legal_mask(int(dealer[b]), calls[:i]), sim['legal'][b, i]))
            self.assertEqual(auction_contract(int(dealer[b]), calls) is not None, bool(sim['contract'][b]))
        hcp = (np.eye(52)[hands].sum(2).reshape(600, 4, 4, 13)[..., 9:] * np.arange(1, 5)).sum((2, 3))[np.arange(600), dealer]
        first = sim['calls'][:, 0]
        for side, low, high in ((0, 12, 14), (1, 13, 15)):
            opened = hcp[(dealer % 2 == side) & (first == bid(1, 'N'))]
            self.assertGreater(len(opened), 5)
            self.assertTrue(low <= opened.min() and opened.max() <= high)
        self.assertGreaterEqual(hcp[(dealer % 2 == 1) & (first == bid(1, 'C'))].min(), 16)        # only East-West play a strong club
        self.assertLess(hcp[(dealer % 2 == 0) & (first == bid(1, 'C'))].min(), 16)                # North-South's 1C is natural

    def test_a_rule_bidder_sees_nothing_from_its_turn_on_and_cannot_make_an_illegal_call(self):
        class Probe(ToyBidder):
            def choose(self, hands, seat, dealer, vul, calls, turn, legal):
                self.seen = calls.copy()
                return np.full(len(hands), bid(1, 'C'))
        probe = Probe()
        session = probe.session(np.arange(13)[None], np.array([0]), np.array([0]), np.array([0]))
        calls = np.array([[PASS, bid(1, 'H'), PASS, PASS, bid(7, 'N')]])
        legal = np.zeros((1, 40), bool)
        legal[0, PASS] = True
        self.assertEqual(session.act(np.array([0]), calls, np.array([2]), legal).tolist(), [PASS])
        self.assertEqual(probe.seen.tolist(), [[PASS, bid(1, 'H'), -1, -1, -1]])
        self.assertIsInstance(session, _RuleSession)

    def test_generators_are_built_and_checked_from_a_package_entry(self):
        options = dict(nt=[12, 14], major=4, strong_club=None)
        entry = dict(kind='toy', options=options, sha256=options_sha256('toy', options))
        self.assertEqual(make_bidder(entry).sha256, TOYS['toy-weak'].sha256)
        with self.assertRaises(ValueError):
            make_bidder(dict(entry, sha256='0' * 64))
        with self.assertRaises(ValueError):
            make_bidder(dict(kind='no-such-engine'))
        with self.assertRaises(ValueError):
            make_bidder(dict(kind='ben-lstm-keras', external=True, path='x.keras'))
        outside = make_bidder(dict(kind='python', factory='bridge_harness.system_bidders:ToyBidder', options=options, sha256=entry['sha256']))
        self.assertIsInstance(outside, ToyBidder)

    def test_neural_adapter_equals_the_engines_bidder_state(self):
        """Needs h5py and the restored house bidders (python models/bidding/<release>/restore_model.py)."""
        try:
            import h5py  # noqa: F401
        except ImportError:
            self.skipTest('h5py is not installed')
        from bridge_harness.gen6_nets import BidderState
        registry = SystemRegistry.load()
        entries = [registry[s].generator() for s in ('house-gen6', 'house-gen5') if s in registry]
        if len(entries) < 2 or not all((ROOT / g['path']).exists() for g in entries):
            self.skipTest('house bidders are not restored')
        pair = tuple(make_bidder(g, ROOT) for g in entries)
        hands, dealer, vul = F.deal(np.random.default_rng(3), 48)
        sim = F.simulate(pair, hands, dealer, vul)
        sessions = [pair[s % 2].session(hands[:, s], np.full(48, s), dealer, vul) for s in range(4)]
        reference = [BidderState(ROOT / g['path']) for g in entries]
        for s in range(4):
            for b in range(48):
                for t in range((s - dealer[b]) % 4, int(sim['length'][b]), 4):
                    got = sessions[s].act(np.array([b]), sim['calls'][b:b + 1].astype(np.int64), np.array([t]), sim['legal'][b:b + 1, t])
                    self.assertEqual(int(got[0]), int(sim['calls'][b, t]))
                auction = tuple(CALLS[c] for c in sim['calls'][b] if c >= 0)
                want = reference[s % 2].final_state(tuple(int(c) for c in hands[b, s]), s, int(dealer[b]), VUL_NAMES[vul[b]], auction)
                self.assertLess(float(np.abs(sessions[s].features[b] - want).max()), 1e-6)


class FitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ids = ['toy-strong', 'toy-weak', 'toy-club']
        cls.train, cls.val = toy_data(1, 400, cls.ids), toy_data(2, 120, cls.ids)
        cls.model = F.Model.new(cls.ids, seed=0, widths=(128, 64, 32))
        F.train(cls.model, cls.train, steps=1200, batch_size=512, log=None)

    def test_data_keeps_each_tables_systems_and_generators(self):
        d = self.train
        self.assertEqual(sorted(str(s) for s in d['systems']), sorted(self.ids))
        self.assertEqual({tuple(t) for t in d['d_sys'].tolist()}, {(a, b) for a in range(3) for b in range(3)})
        for s, g in zip(d['systems'], d['generators']):
            self.assertEqual(str(g), TOYS[str(s)].sha256)
        self.assertTrue(d['label'][d['kind'] == 0].all())                                  # true hands fit their own calls
        self.assertEqual(len(d['label']), len(d['d_dealer']) * 4 * 9)
        other = toy_data(5, 20, ['toy-strong'])
        other['generators'] = np.array(['f' * 64])
        with self.assertRaises(ValueError):
            F.merge([d, other])

    def test_gradients_match_finite_differences(self):
        d = toy_data(7, 15, self.ids)
        model = F.Model.new(self.ids, seed=1, widths=(12, 8, 6))
        rng = np.random.default_rng(0)
        model.p = {k: v.astype(np.float64) for k, v in model.p.items()}
        model.p['Wa'][1:] = rng.standard_normal(model.p['Wa'][1:].shape) * 0.05
        ix = np.sort(rng.choice(len(d['label']), 200, replace=False))
        xh, xa, y, own, opp = F.batch(model, d, ix)
        own, opp = F.view(np.random.default_rng(5), own, opp, (0.5, 0.25, 0.25))
        xh, xa, y = xh.astype(np.float64), xa.astype(np.float64), y.astype(np.float64)
        parts = F.parts_of(xa, model.gate.astype(np.float64), own, opp)
        loss = lambda: F.bce(F.forward(model.p, xh, parts)[0], y)
        out, acts = F.forward(model.p, xh, parts)
        grads = F.gradients(model.p, xh, parts, y, out, acts)
        self.assertEqual({k[1] for k in grads if isinstance(k, tuple)}, {0, 1, 2, 3})
        base, checked, eps = loss(), 0, 1e-5
        for key, g in grads.items():
            arr = model.p['Wa'][key[1]] if isinstance(key, tuple) else model.p[key]
            g = g.reshape(arr.shape)
            for j in rng.choice(np.flatnonzero(np.abs(g) > 1e-4), 6):
                idx = np.unravel_index(j, arr.shape)
                old = arr[idx]
                arr[idx] = old + eps
                up = loss()
                arr[idx] = old - eps
                down = loss()
                arr[idx] = old
                if abs((up - base) - (base - down)) > 1e-3 * abs(up - down):                # a ReLU switches inside the step
                    continue
                self.assertAlmostEqual((up - down) / (2 * eps) / g[idx], 1.0, places=4, msg=str(key))
                checked += 1
        self.assertGreater(checked, 50)

    def test_declaring_the_system_helps_and_declaring_the_wrong_one_costs(self):
        declared, unknown, wrong = (F.evaluate(self.model, self.val, m)['loss'] for m in ('declared', 'unknown', 'wrong'))
        self.assertLess(declared, 0.85 * unknown)
        self.assertLess(unknown, 0.85 * wrong)
        rows = F.by_table(self.model, self.val)
        self.assertEqual(len(rows), 9)
        for r in rows:
            self.assertLess(r['declared']['loss'], r['wrong']['loss'], (r['ns'], r['ew']))

    def test_adding_a_system_leaves_the_others_exactly_as_they_were(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.model.save(Path(tmp) / 'three.npz')
            model = F.Model.load(Path(tmp) / 'three.npz')
            model.add_system('toy-mini')
            model.save(Path(tmp) / 'untrained.npz')
            untrained = SystemFitScorer(Path(tmp) / 'untrained.npz')
            self.assertTrue(np.array_equal(untrained.table('toy-mini', 'toy-weak'), untrained.table(None, 'toy-weak')))   # reads as unknown
            ids4 = self.ids + ['toy-mini']
            new, new_val = toy_data(11, 150, ids4), toy_data(12, 60, ids4)
            at_mini = np.flatnonzero((np.array([str(s) for s in new_val['systems']])[new_val['d_sys'][new_val['deal']]] == 'toy-mini').any(axis=1))
            mini_val = dict(new_val, **{k: new_val[k][at_mini] for k in ('deal', 'seat', 'length', 'hon', 'label', 'kind')})
            before = F.evaluate(model, mini_val)['loss']
            frozen = {k: v.copy() for k, v in model.p.items()}
            F.train(model, new, steps=600, batch_size=512, only=['toy-mini'], log=None)
            for k in F.LAYERS:
                self.assertTrue(np.array_equal(frozen[k], model.p[k]), k)
            self.assertTrue(np.array_equal(frozen['Wa'][:4], model.p['Wa'][:4]))
            self.assertFalse(np.array_equal(frozen['Wa'][4], model.p['Wa'][4]))
            self.assertLess(F.evaluate(model, mini_val)['loss'], 0.95 * before)
            model.save(Path(tmp) / 'four.npz')
            old, grown = SystemFitScorer(Path(tmp) / 'three.npz'), SystemFitScorer(Path(tmp) / 'four.npz')
            member = random_members(200)
            for systems in (TableSystems('toy-strong', 'toy-club'), TableSystems('toy-weak'), TableSystems()):
                a = old.seat_log_score(member, 1, 2, 'EW', AUCTION, systems)
                self.assertTrue(np.array_equal(a, grown.seat_log_score(member, 1, 2, 'EW', AUCTION, systems)))
            with self.assertRaises(ValueError):
                F.train(model, new, steps=1, only=['not-in-model'], log=None)

    def test_a_run_with_validation_data_ends_at_its_best_checked_state(self):
        model = F.Model({k: v.copy() for k, v in self.model.p.items()}, list(self.model.sys_ids))
        start = F.evaluate(model, self.val, n=40000)['loss']
        run = F.train(model, self.train, self.val, steps=40, batch_size=256, lr=(5.0, 5.0), checks=5, log=None)   # a rate that wrecks the net
        after = F.evaluate(model, self.val, n=40000)['loss']
        self.assertLess(run['best_step'], run['steps'])
        self.assertAlmostEqual(after, run['best_loss'], places=6)
        self.assertLessEqual(after, start + 1e-9)
        wrecked = F.Model({k: v.copy() for k, v in self.model.p.items()}, list(self.model.sys_ids))
        F.train(wrecked, self.train, self.val, steps=40, batch_size=256, lr=(5.0, 5.0), keep_best=False, checks=5, log=None)
        self.assertGreater(F.evaluate(wrecked, self.val, n=40000)['loss'], 2 * start)

    def test_starting_from_a_pre_system_scorer_changes_nothing_until_trained(self):
        with tempfile.TemporaryDirectory() as tmp:
            legacy_weights(Path(tmp) / 'old.npz', widths=(16, 8, 8))
            model = F.Model.load(Path(tmp) / 'old.npz')
            for s in self.ids:
                model.add_system(s)
            model.save(Path(tmp) / 'new.npz')
            old, new = FitScorer(Path(tmp) / 'old.npz'), SystemFitScorer(Path(tmp) / 'new.npz')
            member = random_members(200)
            for systems in (TableSystems('toy-strong', 'toy-club'), TableSystems()):
                self.assertTrue(np.array_equal(old.seat_log_score(member, 3, 1, 'Both', AUCTION),
                                               new.seat_log_score(member, 3, 1, 'Both', AUCTION, systems)))

    def test_data_from_a_system_the_model_lacks_trains_the_unknown_reading(self):
        model = F.Model.new(['toy-strong'], seed=0, widths=(16, 8, 8))
        _, _, _, own, opp = F.batch(model, self.train, np.arange(len(self.train['label'])))
        strong = self.train['systems'].tolist().index('toy-strong')
        side = self.train['d_sys'][self.train['deal'], self.train['seat'] % 2]
        self.assertTrue(np.array_equal(own > 0, side == strong))
        self.assertEqual(set(np.unique(own)) | set(np.unique(opp)), {0, 1})


class EngineTests(unittest.TestCase):
    """The bound scorer inside the Gen 6 player. Needs the built solver (scripts/build_dds.py)."""

    def setUp(self):
        from bridge_harness.dds import DDS
        try:
            DDS()
        except RuntimeError:
            self.skipTest('DDS is not built')
        self.env = patch.dict(os.environ, {'BRIDGE_DDS_CACHE': ''})
        self.env.start()
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        from test_gen6 import lead_weights, scorer_weights
        scorer_weights(self.root / 'scorer.npz')
        lead_weights(self.root / 'lead.npz')
        for name in ('belief.npz', 'bidder.keras'):
            (self.root / name).write_bytes(b'x')
        self.players = []

    def tearDown(self):
        for p in self.players:
            p.close()
        self.dir.cleanup()
        self.env.stop()

    def player(self):
        from bridge_harness.gen6 import Gen6Player
        from test_gen6 import FakeBelief, FakeState
        spec = dict(id='6-test', engine='gen6', samples=8, near_tie=0., exploration=0., scorer='scorer.npz', lead_belief='lead.npz',
                    lead_state_bidder='bidder.keras', belief='belief.npz', belief_kind='public', gen6=dict(list_solve=16))
        with patch('bridge_harness.gen6.BidderState', FakeState), patch('bridge_harness.mixed_arena.Weights', FakeBelief):
            p = Gen6Player(spec, self.root)
        self.players.append(p)
        return p

    def table(self, six, board, room):
        from bridge_harness.players import GreedyPlayer
        from bridge_harness.runner import play_table
        result = play_table(board, ['6' if s % 2 == room else 'g' for s in range(4)], {'6': six, 'g': GreedyPlayer()}, seed=5)
        self.assertEqual(result['status'], 'ok', result.get('traceback'))
        return [(a['seat'], a['card'], a.get('estimates')) for a in result['actions']]

    def test_gen6_player_with_a_bound_pre_system_scorer_plays_card_for_card_the_same(self):
        from bridge_harness.corpus import generate
        plain, bound = self.player(), self.player()
        bound.scorer = SystemFitScorer(self.root / 'scorer.npz').bind(TableSystems('any-system', 'another'))
        for seed in (2, 3):
            board = next(generate(1, 700 + seed))
            for room in (0, 1):
                self.assertEqual(self.table(plain, board, room), self.table(bound, board, room))

    def test_gen6_player_runs_on_a_system_aware_file(self):
        from bridge_harness.corpus import generate
        model = F.Model.load(self.root / 'scorer.npz')
        for s in ('a', 'b', 'c'):
            model.add_system(s)
        r = np.random.default_rng(0)
        model.p['Wa'][1:] = (r.standard_normal(model.p['Wa'][1:].shape) * 0.5).astype(np.float32)
        model.save(self.root / 'systems.npz')
        scorer = SystemFitScorer(self.root / 'systems.npz')
        six = self.player()
        board = next(generate(1, 702))
        plays = []
        for systems in (TableSystems('a', 'c'), TableSystems('b', 'a'), TableSystems()):
            six.scorer = scorer.bind(systems)
            plays.append(self.table(six, board, 0))
            self.assertEqual(len(plays[-1]), 52)
        estimates = [[e for _, _, e in table if e] for table in plays]
        self.assertNotEqual(estimates[0], estimates[1])                                    # the declarations reach the layout weights


if __name__ == '__main__':
    unittest.main()
