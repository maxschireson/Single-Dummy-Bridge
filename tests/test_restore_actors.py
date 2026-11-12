"""Anchor restoration imports pinned actors, never another producer's deals or changed retained actors."""
from copy import deepcopy
import json
import shutil
import unittest

from bridge_harness.training import digest
from ops.prepare_gen7_alpha import prepare, restore_missing_actors
import test_gen7_launch as launch_fixture


class RestoreActorTests(unittest.TestCase):
    def setUp(self):
        self.fixture = launch_fixture.Gen7LaunchTests()
        self.fixture.setUp()
        self.root = self.fixture.tmp
        self.source = self.root / 'source'
        self.catalog = self.root / 'catalog'
        shutil.copytree(self.source, self.catalog)
        self.original = deepcopy(self.fixture.old)
        anchor = deepcopy(self.original['bots']['3'])
        anchor.pop('identity');anchor['id'] = 'v1';anchor['identity'] = digest(anchor)
        self.original['bots']['1'] = anchor
        self.original.pop('identity');self.original['identity'] = digest(self.original)
        (self.catalog / 'manifest.json').write_text(json.dumps(self.original))
        self.old = deepcopy(self.original)
        for key in ('1', '5RZ32'):
            del self.old['bots'][key]
        self.old.pop('identity')
        self.old['identity'] = digest(self.old)
        (self.source / 'manifest.json').write_text(json.dumps(self.old))
        self.plan = deepcopy(self.fixture.plan)
        self.plan['roster'] += ['1', '5RZ32']
        self.plan['pair_weights'].update({'7a-32~1': 1, '7a-32~5RZ32': 1})
        self.fixture.plan = self.plan
        self.fixture.write()

    def tearDown(self):
        self.fixture.tearDown()

    def test_preparation_keeps_source_deals_and_all_retained_actors(self):
        run = self.root / 'successor'
        m = prepare(run, self.source, self.fixture.plan_path, restore_actors=self.catalog / 'manifest.json')
        self.assertEqual(m['source_generation'], self.old['identity'])
        self.assertEqual((run / 'corpus.jsonl').read_bytes(), (self.source / 'corpus.jsonl').read_bytes())
        for key, spec in self.original['bots'].items():
            self.assertEqual(m['bots'][key], spec)
        self.assertEqual(set(m['restored_actors']['actors']), {'1', '5RZ32'})
        self.assertEqual(m['labels']['1'], '1')
        self.assertEqual(m['labels']['5RZ32'], self.original['labels']['5RZ32'])
        self.assertEqual(m['restored_actors']['source_manifest'], self.original['identity'])
        self.assertEqual(json.loads((self.source / 'manifest.json').read_text()), self.old)

    def test_valid_but_conflicting_retained_actor_is_refused(self):
        m = deepcopy(self.original)
        m['bots']['6-32']['samples'] += 1
        bot = m['bots']['6-32'];bot.pop('identity');bot['identity'] = digest(bot)
        m.pop('identity');m['identity'] = digest(m)
        (self.catalog / 'manifest.json').write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, 'conflicts with retained actor'):
            restore_missing_actors(self.old, self.plan, self.catalog / 'manifest.json')

    def test_corrupt_model_is_refused_before_preparation(self):
        file = self.catalog / self.original['bots']['1']['bidding']
        file.write_bytes(b'changed model')
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            restore_missing_actors(self.old, self.plan, self.catalog / 'manifest.json')

    def test_catalog_digest_is_required(self):
        m = deepcopy(self.original);m['target'] += 1
        (self.catalog / 'manifest.json').write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, 'catalog manifest changed'):
            restore_missing_actors(self.old, self.plan, self.catalog / 'manifest.json')
