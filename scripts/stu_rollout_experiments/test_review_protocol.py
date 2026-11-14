"""B review: match integrity, role signs and work accounting, no models/boxes.

Run with STU_RUNTIME=/pinned/runtime python FILE -v.
--strict-known exposes the resume-invariant failure rather than marking it known.
"""
from concurrent.futures import Future
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

runtime = Path(os.environ['STU_RUNTIME']).resolve()
sys.path[:0] = [str(runtime), str(runtime / 'scripts'), str(runtime / 'tests')]
import gen8_match as gm
import x8_match as xm


class FakePool:
    outcomes = []
    def __init__(self, *args, **kwargs):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def submit(self, *args):
        future = Future()
        result = self.outcomes.pop(0)
        if isinstance(result, Exception):
            future.set_exception(result)
        else:
            future.set_result(result)
        return future


class ProtocolReview(unittest.TestCase):
    def row(self, index=0):
        return dict(index=index, family='fixture-family', cpu=.2, common=1., native=1.)

    def run_main(self, out, outcomes):
        manifest = dict(identity='new-spec', roster=['rx-a', 'rx-b'])
        FakePool.outcomes = list(outcomes)
        args = ['review', '--source', str(out), '--pair', 'rx-a~rx-b', '--deals', '1',
                '--seed', '2026111401', '--workers', '1', '--out', str(out)]
        log = io.StringIO()
        with patch.object(sys, 'argv', args), patch.object(gm, 'build_manifest', return_value=manifest), \
             patch.object(gm.os, 'popen', return_value=io.StringIO('fixture-source\n')), \
             patch.object(gm, 'ProcessPoolExecutor', FakePool), redirect_stdout(log):
            gm.main()
        return json.loads((out / 'summary.json').read_text()), log.getvalue()

    @unittest.expectedFailure
    def test_resume_rejects_different_manifest_before_relabelling_old_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            (out / 'manifest.json').write_text(json.dumps(dict(identity='old-spec')))
            (out / 'results.jsonl').write_text(json.dumps(self.row()) + '\n')
            with self.assertRaises((ValueError, RuntimeError, SystemExit)):
                self.run_main(out, [])

    def test_successful_retry_erases_failure_from_final_summary_but_not_stdout(self):
        with tempfile.TemporaryDirectory() as temp:
            summary, log = self.run_main(Path(temp), [RuntimeError('transient sentinel'), self.row()])
        self.assertEqual(summary['boards'], 1)
        self.assertEqual(summary['failures'], 0)
        self.assertIn('failed (attempt 1)', log)

    def test_twice_failed_board_remains_missing_and_is_counted(self):
        with tempfile.TemporaryDirectory() as temp:
            summary, log = self.run_main(Path(temp), [RuntimeError('one'), RuntimeError('two')])
        self.assertEqual(summary['boards'], 0)
        self.assertEqual(summary['failures'], 1)

    def test_rollout_summary_omits_child_work_retained_on_action(self):
        action = dict(role='candidate', gen6={}, recursive=dict(calls=2, net_rows=70),
            x8=dict(mode='rollout', n=[2, 2], net_rows=10, chosen='SA', runs=[['SA']], seconds={}))
        got = xm.summarise_actions({'t': dict(tables=[dict(actions=[action])])}, ['candidate'])
        self.assertEqual(got['candidate']['x8']['net_rows'], 10)
        self.assertNotIn('recursive', got['candidate'])
        self.assertEqual(action['recursive']['net_rows'], 70)

    def test_common_bidder_is_reused_by_every_spec(self):
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
    if '--strict-known' in sys.argv:
        sys.argv.remove('--strict-known')
        ProtocolReview.test_resume_rejects_different_manifest_before_relabelling_old_rows.__unittest_expecting_failure__ = False
    unittest.main()
