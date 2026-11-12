from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import unittest

from bridge_harness.corpus import generate
from bridge_harness.improvement import Campaign, initialize, read, writer_lock, validate_record
from bridge_harness.loop_registry import freeze_bot, verify_bot, build_player
from bridge_harness.loop_stats import gate, plan_arena
from bridge_harness.runner import run_pair
from bridge_harness.training import digest

ROOT = Path(__file__).resolve().parents[1]


def settings():
    def spec(player):
        return dict(factory=f'bridge_harness.players:{player}',kwargs={},budget={'objective':'tricks'},artifacts={})
    return dict(campaign_id='test-001',seed=39,initial='v2',original='v1',ben='ben',smoke=True,
                training_stages=[4,8],evaluation_looks=[4,8],shard_size=4,workers=2,
                board_timeout=30,arena_board_timeout=30,command_timeout=60,
                family_alpha=.05,minimum_imp_gain=0.,exclusion_files=[],corpus_command=None,
                trainer_command=[sys.executable,str(ROOT/'tests/loop_fixture_trainer.py'),'{request}'],
                bots=dict(v1=spec('RandomPlayer'),v2=spec('GreedyPlayer'),ben=spec('RandomPlayer')))


class GateTests(unittest.TestCase):
    def test_effect_size_planning_scales_quadratically(self):
        a=plan_arena(.1,2,3);b=plan_arena(.05,2,3)
        self.assertAlmostEqual(b['recommended_arena_deals']/a['recommended_arena_deals'],4.,delta=.05)
        self.assertGreater(a['endpoint_deals']['improvement_vs_ben'],a['endpoint_deals']['vs_parent'])
        with self.assertRaises(ValueError):plan_arena(0,2,3)

    def rows(self, parent=1., ben_gain=1.):
        return [dict(deal_id=str(i),vs_parent=parent+(i%2)*.02,
                     vs_original=2.+(i%3)*.01,vs_ben=-3.+ben_gain+(i%2)*.02,
                     parent_vs_ben=-3.) for i in range(2000)]

    def test_ben_need_not_be_beaten_outright(self):
        g=gate(self.rows(),1,3,3)
        self.assertEqual(g['decision'],'promote')
        self.assertLess(g['descriptive']['vs_ben']['mean'],0)
        self.assertGreater(g['improvement_vs_ben']['low'],0)

    def test_both_endpoints_required(self):
        self.assertEqual(gate(self.rows(1,-1),1,3,3)['decision'],'futile')
        self.assertEqual(gate(self.rows(-1,1),1,3,3)['decision'],'futile')

    def test_all_ties_cannot_promote(self):
        rows=self.rows()
        for r in rows: r.update(vs_parent=0,vs_ben=-3,parent_vs_ben=-3)
        self.assertEqual(gate(rows,1,3,3)['decision'],'inconclusive')

    def test_no_false_precision_from_repeat_deals(self):
        rows=self.rows(); rows[1]['deal_id']=rows[0]['deal_id']
        with self.assertRaisesRegex(ValueError,'Repeated'): gate(rows,1,3,3)

    def test_alpha_budget_and_paired_ben_delta(self):
        rows=self.rows()
        for i,r in enumerate(rows):
            r['vs_ben'] += 10*(i%2); r['parent_vs_ben'] += 10*(i%2)
        a=gate(rows,1,3,3); b=gate(rows,2,3,3)
        self.assertAlmostEqual(a['improvement_vs_ben']['mean'],1.01)
        self.assertAlmostEqual(b['adjusted_alpha'],a['adjusted_alpha']/3)


class RegistryTests(unittest.TestCase):
    def test_manifest_auction_weights_play_complete_dds_game(self):
        import numpy as np
        from bridge_harness.auction_belief import CALLS
        with tempfile.TemporaryDirectory() as td:
            shapes=[(len(CALLS)+1,4),(5,2),(448,64),(64,),(64,64),(64,),(64,208),(208,)]
            weights=Path(td)/'zero.npz'
            np.savez_compressed(weights,**{f'w{i}':np.zeros(shape,np.float32) for i,shape in enumerate(shapes)})
            spec=dict(factory='bridge_harness.loop_registry:auction_pimc',
                      kwargs=dict(weights='$artifact:belief',samples=2,objective='tricks',near_tie=.125),
                      budget=dict(samples=2,objective='tricks'),artifacts=dict(belief=str(weights)))
            path=freeze_bot(td,'weighted',spec)
            player='manifest:'+str(path)
            cfg=dict(mode='selfplay',candidate=player,baseline=player,common=player)
            board=next(generate(1,876))
            record=run_pair(board,cfg);validate_record(record,board,cfg)
            self.assertEqual(len(record['tables'][0]['actions']),52)
            self.assertTrue(any(a.get('dds_calls')==2 for a in record['tables'][0]['actions']))

    def test_immutable_weights_and_name(self):
        with tempfile.TemporaryDirectory() as td:
            weight=Path(td)/'weight.bin'; weight.write_bytes(b'fixed')
            spec=settings()['bots']['v2']; spec['artifacts']={'unused':str(weight)}
            path=freeze_bot(td,'v2',spec); identity=verify_bot(path)['identity']
            self.assertTrue(hasattr(build_player(path),'choose'))
            weight.write_bytes(b'modified outside registry')
            self.assertEqual(verify_bot(path)['identity'],identity)
            with self.assertRaisesRegex(ValueError,'Immutable'): freeze_bot(td,'v2',spec)
            (path.parent/'artifacts/unused.bin').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError,'Artifact'): verify_bot(path)

    def test_lock_excludes_second_writer(self):
        with tempfile.TemporaryDirectory() as td:
            with writer_lock(td):
                with self.assertRaisesRegex(RuntimeError,'writer'):
                    with writer_lock(td): pass
            with writer_lock(td): pass


class CampaignTests(unittest.TestCase):
    def test_source_and_settings_changes_block_preflight(self):
        with tempfile.TemporaryDirectory() as td:
            initialize(td,settings());c=Campaign(td)
            try:
                original=deepcopy(c.config)
                c.config['source_sha256']='different'
                with self.assertRaisesRegex(ValueError,'Code/solver'):c.preflight()
                c.config=original;c.config['settings']['seed']+=1
                with self.assertRaisesRegex(ValueError,'settings changed'):c.preflight()
            finally:c.close()

    def test_unchanged_weights_skip_expensive_arena(self):
        with tempfile.TemporaryDirectory() as td:
            s=settings();s['trainer_command'].append('--copy-parent');initialize(td,s);c=Campaign(td)
            try:
                self.assertEqual(c.run()['status'],'exhausted')
                self.assertFalse(list(Path(td).glob('g*/arena-*')))
                self.assertEqual([r['decision'] for r in read(Path(td)/'progress.json')['candidates']],['unchanged']*2)
            finally:c.close()

    def test_full_smoke_loop_and_cached_resume(self):
        with tempfile.TemporaryDirectory() as td:
            initialize(td,settings()); c=Campaign(td)
            try:
                self.assertTrue(c.preflight()['ready'])
                state=c.run()
                self.assertEqual(state['status'],'exhausted')
                self.assertEqual(state['champion'],'v2')
                self.assertEqual(state['promotions'],[])
                data4=read(Path(td)/'g1/dataset-4.json'); data8=read(Path(td)/'g1/dataset-8.json')
                self.assertEqual(data4['shards'],data8['shards'][:1])
                games=list(Path(td).rglob('*.json.gz'))
                timestamps={str(p):p.stat().st_mtime_ns for p in games}
                c.collect(1,8,'v2')
                latest=read(Path(td)/'progress.json')['candidates'][-1]
                c.arena(1,8,'candidate-g1-n8','v2',latest['evaluation_deals'])
                self.assertEqual(timestamps,{str(p):p.stat().st_mtime_ns for p in games if not p.name.startswith('rows-')}
                                 | {str(p):timestamps[str(p)] for p in games if p.name.startswith('rows-')})
                self.assertIn('SMOKE TEST', (Path(td)/'progress.md').read_text())
                with self.assertRaisesRegex(ValueError,'exhausted'): c.run()
                with self.assertRaisesRegex(ValueError,'production'): c.promote({'decision':'promote'})
            finally:c.close()

    def test_duplicate_and_train_arena_overlap_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            initialize(td,settings()); c=Campaign(td)
            try:
                boards=list(generate(2,71))
                c.reserve(boards,'selfplay','one'); c.reserve(boards,'selfplay','one')
                with self.assertRaisesRegex(ValueError,'overlap'):c.reserve(boards,'arena','two')
                with self.assertRaisesRegex(ValueError,'independent'):c.reserve([replace(boards[0],family='related')],'selfplay','one')
            finally:c.close()

    def test_failed_pair_blocks_and_explicit_retry_preserves_failure(self):
        from bridge_harness.selfplay import atomic_json
        with tempfile.TemporaryDirectory() as td:
            initialize(td,settings()); c=Campaign(td)
            try:
                b=next(generate(1,72)); path=Path(td)/'bad.json.gz'
                atomic_json(path,{'status':'timeout'},True)
                with self.assertRaises((KeyError,RuntimeError)):c.pair(b,'v2','v1',path)
                result=c.pair(b,'v2','v1',path,retry=True)
                self.assertEqual(result['status'],'ok')
                self.assertEqual(len(list(Path(td).glob('bad.json.gz.failed-*'))),1)
            finally:c.close()

    def test_changed_corpus_blocks_resume(self):
        with tempfile.TemporaryDirectory() as td:
            initialize(td,settings()); c=Campaign(td)
            try:
                c.corpus('g1/test',4,'arena')
                path=Path(td)/'g1/test/auction/frozen.jsonl';path.write_text(path.read_text()+'\n')
                with self.assertRaisesRegex(ValueError,'changed'):c.corpus('g1/test',4,'arena')
            finally:c.close()

    def test_unbound_trainer_and_bad_sizes_fail(self):
        with tempfile.TemporaryDirectory() as td:
            s=settings();s['trainer_command']=None;initialize(td,s);c=Campaign(td)
            try:
                with self.assertRaisesRegex(ValueError,'trainer_command'):c.preflight()
            finally:c.close()
        with tempfile.TemporaryDirectory() as td:
            s=settings();s['shard_size']=0
            with self.assertRaises(ValueError):initialize(td,s)

    def test_non_smoke_requires_real_ben_and_auction_binding(self):
        with tempfile.TemporaryDirectory() as td:
            s=settings();s['smoke']=False;initialize(td,s);c=Campaign(td)
            try:
                with self.assertRaisesRegex(ValueError,'corpus_command'):c.preflight()
            finally:c.close()

    def test_score_and_player_tampering_are_rejected(self):
        b=next(generate(1,73));config=dict(candidate='greedy',baseline='random',mode='partnership')
        record=run_pair(b,config);validate_record(record,b,config)
        bad=deepcopy(record);bad['imps']+=1
        with self.assertRaisesRegex(ValueError,'IMP'):validate_record(bad,b,config)
        bad=deepcopy(record);bad['tables'][0]['actions'][0]['player']='wrong'
        with self.assertRaisesRegex(ValueError,'player'):validate_record(bad,b,config)


if __name__=='__main__':unittest.main()
