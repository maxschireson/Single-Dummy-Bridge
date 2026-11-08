import unittest
from collection_slices import bounded_slice, SliceComplete
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'tests'))


class SliceTests(unittest.TestCase):
    def test_drain_and_stop(self):
        clock = [0]
        seen = []
        def work(n):
            seen.append(n)
            clock[0] = 10
            return n
        with self.assertRaises(SliceComplete):
            list(bounded_slice(work, range(20), 1, 5, lambda: clock[0]))
        self.assertEqual(seen, [0])

    def test_finish_last_board_after_deadline(self):
        clock = [0]
        def work(n):
            clock[0] = 10
            return n
        self.assertEqual(list(bounded_slice(work, [1], 1, 5, lambda: clock[0])), [1])

    def test_errors_are_not_retried(self):
        def work(n):
            raise ValueError('invalid record')
        with self.assertRaisesRegex(ValueError, 'invalid record'):
            list(bounded_slice(work, range(20), 1, 5, lambda: 0))

    def test_all_jobs(self):
        self.assertEqual(sorted(bounded_slice(lambda n: n, range(20), 3, 5, lambda: 0)), list(range(20)))

    def test_process_handoff_preserves_completed_records(self):
        from test_improvement import settings
        from bridge_harness.improvement import initialize
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = settings()
            config['training_stages'] = [32]
            initialize(root, config)
            env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
            command = [sys.executable, str(REPO/'ops/collection_slices.py'), 'slice',
                       '--root', td, '--seconds', '1', '--workers', '1']
            first = subprocess.run(command, cwd=REPO, env=env, capture_output=True, timeout=45)
            self.assertEqual(first.returncode, 0, first.stderr.decode())
            files = list(root.glob('g1/selfplay/*/episodes/*.json.gz'))
            self.assertGreater(len(files), 0)
            self.assertLess(len(files), 32)
            original = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
            command[2] = 'supervise'
            resumed = subprocess.run(command, cwd=REPO, env=env, capture_output=True, timeout=90)
            self.assertEqual(resumed.returncode, 0, resumed.stderr.decode())
            events = [json.loads(line) for line in (root/'slice-events.jsonl').read_text().splitlines()]
            self.assertGreaterEqual(sum(e['event']=='child_start' for e in events), 2)
            self.assertEqual(events[-1]['event'], 'ready_for_campaign_runner')
            self.assertEqual(len(list(root.glob('g1/selfplay/*/episodes/*.json.gz'))), 32)
            for path, expected in original.items():
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main()
