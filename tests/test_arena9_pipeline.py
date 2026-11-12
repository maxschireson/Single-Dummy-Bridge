"""Tests for the arena's experience pipeline and arrival (bridge_harness/arena9_pipeline.py, G9-D7) and the comparison
floors of bridge_harness/arena9.py (G9-D6). No DDS, no nets: profile evidence is stubbed where it would load them."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness import arena9 as a9  # noqa: E402
from bridge_harness import arena9_pipeline as pl  # noqa: E402
from bridge_harness import experience as xp  # noqa: E402
from bridge_harness import experience_store as xs  # noqa: E402
from bridge_harness.player_model import PlayerModel  # noqa: E402

RULES = dict(schema='arena-rules-v1', version='test', condition='native', reference='anchor',
             promotion=dict(alpha=0.05, beta=0.10, d=0.1, cap=10000), admission=dict(se=0.15, max_boards=2000),
             retirement=dict(min_epochs=1, gap=1.0), shares=dict(training=0.55, promotion=0.20, panel=0.15, admission=0.10),
             epoch=dict(boards=60), weight_units=100, max_weight_ratio=2,
             floors=[dict(pairs=['g9~guest', 'ctl~guest'], boards=10, same_deals=True)])
CARDING = json.loads((ROOT / 'configs/carding/guest-a.json').read_text())['declared']


def package(pid, kind, strength, **extra):
    return dict(dict(schema='player-package-v1', id=pid, label=pid, kind=kind, bundle=dict(source='sim', sim=dict(strength=strength)),
                     declaration=dict(profiles={'house-gen6': 1.0}) if kind != 'guest' else dict(carding=CARDING),
                     lineage=dict(training_families={}), needs={}, licence='redistributable'), **extra)


class Signaller(a9.SimBackend):
    """Synthetic boards whose guest leaves one card.<key> occasion a board: prescribed card in 8 of 10 boards."""

    def play(self, m, pair, indices, seed, workers=1):
        for idx, row in super().play(m, pair, indices, seed, workers):
            if 'guest' in pair.split('~') and row['common'] is not None:
                hit = idx % 10 < 8
                d = xp.delta('guest', f"{m['id'][:12]}/{pair}/{idx}", {'card.partner_lead.attitude': xp.count(**{'all/2': 1, 'hit/2': int(hit)})})
                row = dict(row, envelopes=[xs.envelope(d, 'sim', row['completed_epoch'], xs.occasion(row['family'], pair, ['x']))])
            yield idx, row


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.pkgs = {p['id']: p for p in (package('ctl', 'house', 0.0), package('g9', 'house', 0.2), package('anchor', 'anchor', -1.0),
                                          package('guest', 'guest', -0.3))}

    def tearDown(self):
        shutil.rmtree(self.dir)

    def control(self, only, rules=RULES):
        c = self.dir / 'c'
        a9.init(c, {k: v for k, v in self.pkgs.items() if k in only}, rules, 'ctl', 'test', 'unit test',
                arrival=lambda p: pl.arrival_model(p, ROOT, distances=lambda card: dict(rates={})))
        return c


class Floors(Base):
    def test_floor_pairs_play_the_same_deals_and_fill_their_share(self):
        c = self.control(('ctl', 'g9', 'anchor', 'guest'))
        m = a9.current(c)
        self.assertEqual(m['schedule']['floors'][0]['pairs'], ['g9~guest', 'ctl~guest'])
        self.assertIn('guest', m['players'])
        a9.play_epoch(c, a9.SimBackend(self.pkgs))
        rows = [json.loads(l) for l in (c / 'results' / 'e0001' / 'slot0.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows), RULES['epoch']['boards'])
        fl = [r for r in rows if r['floor'] == 0]
        self.assertEqual(len(fl), 20)
        a = sorted(r['family'] for r in fl if r['pair'] == 'g9~guest')
        b = sorted(r['family'] for r in fl if r['pair'] == 'ctl~guest')
        self.assertEqual(a, b)                                              # the same deals for the bot and its control
        self.assertEqual(len(set(a)), 10)
        self.assertEqual(len({(r['k'], r['slot']) for r in rows}), len(rows))
        self.assertTrue(all(r['experience_snapshot'] == m['experience_snapshot'] for r in rows))

    def test_a_floor_waits_for_its_players(self):
        c = self.control(('ctl', 'g9', 'anchor'))
        self.assertEqual(a9.current(c)['schedule']['floors'], [])
        (c / 'queue' / '0-submit-guest.json').write_text(json.dumps(a9.event('submit', 'guest', 'max', 'unit test')))
        a9.play_epoch(c, a9.SimBackend(self.pkgs))
        nxt, _ = a9.close_epoch(c, self.pkgs, arrival=lambda p: pl.arrival_model(p, ROOT, distances=lambda card: dict(rates={})))
        self.assertEqual(len(nxt['schedule']['floors']), 1)
        self.assertEqual(nxt['players']['guest']['model']['carding'], CARDING)

    def test_floors_larger_than_an_epoch_are_refused(self):
        with self.assertRaises(ValueError):
            self.control(('ctl', 'g9', 'anchor', 'guest'), rules=dict(RULES, epoch=dict(boards=10)))


class Experience(Base):
    def test_the_reader_in_epoch_2_is_handed_epoch_1_and_nothing_later(self):
        c = self.control(('ctl', 'g9', 'anchor', 'guest'))
        backend = Signaller(self.pkgs)
        a9.play_epoch(c, backend)
        a9.close_epoch(c, self.pkgs)
        a9.play_epoch(c, backend)                                        # epoch 2's boards are played, epoch 2 not yet closed
        envs = xs.read(sorted(c.glob('results/e*/experience-*.jsonl')))
        e1 = [e for e in envs if e['epoch'] == 1]
        self.assertTrue(e1 and any(e['epoch'] == 2 for e in envs))
        rep = pl.epoch_experience(c, 2)
        g = rep['players']['guest']
        self.assertTrue(g['snapshot_matches_envelopes'])
        self.assertEqual(g['boards'], len(e1))                             # epoch 1's guest boards, none of epoch 2's
        snap = xs.load_snapshot(c / 'snapshots' / f"{a9.current(c)['experience_snapshot']}.json.gz")
        n = snap['players']['guest']['stats']['card.partner_lead.attitude']['n']
        hits = sum(1 for e in e1 if e['delta']['stats']['card.partner_lead.attitude']['n']['hit/2'])
        self.assertEqual((n['all/2'], n['hit/2']), (len(e1), hits))
        from bridge_harness.gen9_play import experience_honesty
        model = PlayerModel.from_dict(pl.table_models(a9.current(c), snap)['guest'])
        self.assertAlmostEqual(g['honesty_read']['*'], experience_honesty(model, 0.05)['*'], places=4)

    def test_table_models_name_the_snapshot_and_give_a_newcomer_an_empty_one(self):
        c = self.control(('ctl', 'g9', 'anchor', 'guest'))
        m = a9.current(c)
        snap = xs.load_snapshot(c / 'snapshots' / f"{m['experience_snapshot']}.json.gz")
        models = pl.table_models(m, snap)
        self.assertEqual(set(models), set(m['players']))
        for md in models.values():
            pm = PlayerModel.from_dict(md)
            self.assertEqual((pm.snapshot, pm.boards), (m['experience_snapshot'], 0))
        self.assertEqual(dict(PlayerModel.from_dict(models['g9']).profiles), {'house-gen6': 1.0})


class Arrival(unittest.TestCase):
    def test_a_guest_with_a_card_gets_arrive_and_a_house_bot_its_profiles(self):
        card = json.loads((ROOT / 'configs/cards/rb-precision.json').read_text())
        guest = dict(id='g', kind='guest', declaration=dict(card='configs/cards/rb-precision.json', carding=CARDING))
        m = pl.arrival_model(guest, ROOT, distances=lambda c: dict(rates={'house-gen5': 0.2628, 'house-gen6': 0.2719}))
        probs = dict(map(tuple, m['profiles']))
        self.assertGreater(probs['card'], 0.75)
        self.assertLess(probs['house-gen6'], 0.01)
        self.assertEqual((m['bidding']['id'], m['carding']), (card['id'], CARDING))
        self.assertEqual(m['arrival']['source'], 'player_model.arrive')
        house = pl.arrival_model(dict(id='h', kind='house', declaration=dict(profiles={'house-gen6': 1.0})), ROOT)
        self.assertEqual(house['profiles'], [['house-gen6', 1.0]])

    def test_the_matrix_supplies_the_distances_it_has(self):
        d = pl.Distances(ROOT, systems=('house-gen5', 'house-gen6'))
        out = d(json.loads((ROOT / 'configs/cards/rb-precision.json').read_text()))
        self.assertAlmostEqual(out['rates']['house-gen5'], 0.2628)
        self.assertEqual(set(out['source'].values()), {pl.MATRIX})


class BoardDeltas(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((ROOT / 'tests/data/arena9_board_record.json').read_text())
        self.saved = dict(pl._CACHE)
        pl._CACHE.update(systems={}, flat=None)                          # no nets: bidding deltas without profile evidence

    def tearDown(self):
        pl._CACHE.clear(); pl._CACHE.update(self.saved)

    def test_statistics_go_to_whoever_bid_and_whoever_played(self):
        card = json.loads((ROOT / 'configs/cards/rb-precision.json').read_text())
        decl = {'guest-a': dict(card=card, carding=CARDING, kind='guest', profiles=None),
                '9a-32': dict(card=None, carding=None, kind='house', profiles={'house-gen6': 1.0})}
        envs = pl.board_envelopes(self.record, 'k', {}, decl, 'test', 1.0, root=str(ROOT))
        self.assertTrue(envs)
        self.assertEqual({e['delta']['player'] for e in envs}, {'guest-a'})   # the house bot declared nothing to learn
        bid = [e for e in envs if e['delta']['key'].endswith('/bid')]
        native = {b['table'] for k, b in self.record['bidding'].items() if k.startswith('native')}
        self.assertTrue(bid and {e['delta']['key'].split('/')[1] for e in bid} <= native)   # guest-a bid only at native tables
        self.assertTrue(all(any(s.startswith('bid.') for s in e['delta']['stats']) for e in bid))
        card_env = [e for e in envs if e['delta']['key'].endswith('/card')]
        self.assertTrue(card_env and all(any(s.startswith('card.') for s in e['delta']['stats']) for e in card_env))
        self.assertEqual(len({e['delta']['key'] for e in envs}), len(envs))
        stores, report = xs.merge(envs)
        self.assertEqual(stores['guest-a']['boards'] + len(report['occasion_repeats']), len(envs))

    def test_the_trace_changes_with_any_card(self):
        t = pl.trace(self.record)
        other = json.loads(json.dumps(self.record))
        acts = other['unique_tables']['table-0']['tables'][0]['actions']
        acts[0]['card'], acts[1]['card'] = acts[1]['card'], acts[0]['card']
        self.assertNotEqual(t, pl.trace(other))
        self.assertEqual(t, pl.trace(json.loads(json.dumps(self.record))))


if __name__ == '__main__':
    unittest.main()
