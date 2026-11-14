"""Coordinator regressions for B03/B06-B11; original audit remains in PR #43.

The corrected runner refuses all nonempty output directories, uses one attempt,
and retains native costs and child counters. These tests target that runner,
not the unchanged historical gen8_match.main.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

runtime = Path(os.environ['STU_RUNTIME']).resolve()
sys.path[:0] = [str(Path(__file__).parent), str(runtime), str(runtime / 'scripts')]
import match as runner
from engine import ExperimentalPlayer


class ProtocolReview(unittest.TestCase):
    def test_ben_worker_endpoint_does_not_mutate_frozen_manifest(self):
        from queue import Queue
        endpoints = Queue()
        endpoints.put('http://127.0.0.1:8182')
        m = dict(bots={'ben64': dict(engine='ben', url='http://127.0.0.1:8181')})
        with patch.object(runner.gm, 'start') as start:
            runner.start_worker('/fixture', m, endpoints)
        self.assertEqual(m['bots']['ben64']['url'], 'http://127.0.0.1:8181')
        self.assertEqual(start.call_args.args[1]['bots']['ben64']['url'], 'http://127.0.0.1:8182')

    def test_ben_time_reports_external_cpu_as_unmeasured(self):
        from bridge_harness.players import Decision
        p = runner.TimedBen('http://127.0.0.1:8181', samples=64)
        with patch.object(runner.Round5BenPlayer, 'choose', return_value=Decision(2, {})):
            r = p.choose(None, None)
        self.assertGreaterEqual(r.details['experiment_work']['wall_seconds'], 0)
        self.assertFalse(r.details['experiment_work']['external_server_cpu_measured'])
        self.assertNotIn('inclusive_cpu_seconds', r.details['experiment_work'])

    def test_resume_refused_without_relabelling_or_changing_old_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            for name, data in [('manifest.json', '{"identity":"old"}'), ('results.jsonl', '{"index":1}\n')]:
                (out / name).write_text(data)
            before = {p.name: p.read_bytes() for p in out.iterdir()}
            with self.assertRaisesRegex(ValueError, 'fresh run identity'):
                runner.prepare_output(out, {'identity': 'new'})
            self.assertEqual(before, {p.name: p.read_bytes() for p in out.iterdir()})

    def test_fresh_identity_exclusively_created_and_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            runner.prepare_output(temp, {'identity': 'new'})
            with self.assertRaises(ValueError):
                runner.prepare_output(temp, {'identity': 'new'})

    def test_failed_first_attempt_keeps_cost_and_error_without_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            runner.prepare_output(temp, {})
            with patch.object(runner.gm, 'play', side_effect=RuntimeError('sentinel')) as play:
                with self.assertRaisesRegex(RuntimeError, 'sentinel'):
                    runner.attempt(9, 42, temp, False)
                self.assertEqual(play.call_count, 1)
            ledger = json.loads((Path(temp)/'attempts/000009.json').read_text())
            self.assertEqual(ledger['status'], 'failed')
            self.assertGreaterEqual(ledger['wall_seconds'], 0)
            report = runner.summarize([], 'a~b', temp)
            self.assertEqual(report['failures'], 1)
            self.assertEqual(report['attempts'], 1)

    def test_attempt_includes_external_cpu_after_player_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            runner.prepare_output(temp, {})
            with patch.object(runner.gm, 'play', return_value={'index': 9}), \
                 patch.object(runner, 'child_cpu', side_effect=[1., 4.5]):
                row = runner.attempt(9, 42, temp, False)
            self.assertEqual(row['attempt_work']['solver_cpu_seconds'], 3.5)
            self.assertGreaterEqual(row['attempt_work']['inclusive_cpu_seconds'], 3.5)

    def test_summary_retains_child_work_and_actual_precision(self):
        action = dict(role='candidate', gen6={}, recursive=dict(calls=2, net_rows=70, changed=3),
            experiment_work=dict(wall_seconds=5., solver_cpu_seconds=2., precision='bf16', rollout_precision='bf16'),
            x8=dict(mode='rollout', n=[2, 2], net_rows=10, chosen='SA', runs=[['SA']], seconds={}))
        got = runner.summarise_actions({'t': dict(tables=[dict(actions=[action])])}, ['candidate'])
        self.assertEqual(got['candidate']['recursive']['net_rows'], 70)
        self.assertEqual(got['candidate']['experiment_work']['solver_cpu_seconds'], 2.)
        self.assertEqual(got['candidate']['precisions'], [['bf16', 'bf16']])

    def test_actor_costs_follow_actual_actor_when_row_order_reverses(self):
        rows = [dict(index=0, cpu=1, candidate='b', opponent='a',
            search=dict(candidate=dict(experiment_work={'wall_seconds': 3}), opponent=dict(experiment_work={'wall_seconds': 2})))]
        with tempfile.TemporaryDirectory() as temp:
            runner.prepare_output(temp, {})
            result = runner.summarize(rows, 'a~b', temp)
        self.assertEqual(result['actors']['a']['work']['wall_seconds'], 2)
        self.assertEqual(result['actors']['b']['work']['wall_seconds'], 3)

    def test_engine_hash_is_checked_before_loading_any_model(self):
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            ExperimentalPlayer({'rollout_experiment': {'implementation_sha256': 'wrong'}}, '/missing')

    def test_common_bidder_is_reused_by_every_spec(self):
        gm = runner.gm
        m = dict(common_only=True, common_bidder='common', bots={
            'common': dict(bidding='bidder.npz'), 'rx-a': dict(bidding='wrong-a'),
            'rx-b': dict(bidding='wrong-b')})
        saved_state = dict(gm.STATE)
        original_auction = gm.gen5_arena.auction
        bidder = object()
        try:
            with patch.object(gm, 'NumpyPolicy', return_value=bidder) as factory:
                gm.start('/fixture', m)
            self.assertEqual(factory.call_count, 1)
            self.assertTrue(all(x is bidder for x in gm.STATE['bidders'].values()))
        finally:
            gm.STATE.clear()
            gm.STATE.update(saved_state)
            gm.gen5_arena.auction = original_auction

    def test_row_sign_is_first_named_actor_when_candidate_order_reverses(self):
        gm = runner.gm
        saved = dict(gm.STATE)
        record = dict(candidate='rx-b', opponent='rx-a', family='fixture', unique_tables={},
                      board={}, regimes=dict(common=dict(imps=3, score_difference=120)))
        gm.STATE.update(m=dict(roster=['rx-a', 'rx-b']), source='/fixture', book=None, deals=None)
        gm.STATE.setdefault('bidders', {})
        try:
            with patch.object(gm, 'run_board', return_value=record), \
                 patch.object(gm, 'summarise_actions', return_value={}):
                row = gm.play(0, 2026111401, None)
            self.assertEqual(row['common'], -3)
            self.assertEqual(row['common_score'], -120)
        finally:
            gm.STATE.clear()
            gm.STATE.update(saved)


if __name__ == '__main__':
    unittest.main()
