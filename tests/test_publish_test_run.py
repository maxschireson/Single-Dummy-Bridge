"""The test-run publisher against a local bare repository. Does not exercise GitHub or SSH."""
import gzip
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'ops' / 'publish_test_run.py'


class PublishTestRun(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.remote = self.tmp / 'remote.git'
        subprocess.run(['git', 'init', '--bare', '-q', str(self.remote)], check=True)
        self.run_dir = self.tmp / 'runs' / 'match-a'
        for folder in ('episodes', 'receipts', 'failures', 'artifacts'):
            (self.run_dir / folder).mkdir(parents=True)
        (self.run_dir / 'manifest.json').write_text(json.dumps(dict(identity='x')))
        (self.run_dir / 'corpus.jsonl').write_text('{}\n')
        (self.run_dir / 'dds-cache.sqlite').write_bytes(b'cache')
        (self.run_dir / 'artifacts' / 'model.npz').write_bytes(b'model')
        self.plan = self.tmp / 'plan.json'
        self.plan.write_text('{"title": "t"}')
        self.readme = self.tmp / 'README.md'
        self.readme.write_text('# data\n')
        self.board(0)

    def tearDown(self):
        self._tmp.cleanup()

    def board(self, i):
        with gzip.open(self.run_dir / 'episodes' / f'{i:06d}.json.gz', 'wt') as f:
            json.dump(dict(index=i), f)
        (self.run_dir / 'receipts' / f'{i:06d}.json').write_text(json.dumps(dict(index=i)))
        (self.run_dir / 'state.json').write_text(json.dumps(dict(completed=i + 1)))

    def publish(self, *extra, branch='transfer/unit-test'):
        return subprocess.run([sys.executable, str(TOOL), '--run', str(self.run_dir), '--branch', branch,
                               '--checkout', str(self.tmp / 'pub'), '--remote', self.remote.as_uri(), '--plan', str(self.plan),
                               '--readme', str(self.readme), *extra], capture_output=True, text=True, timeout=120)

    def remote_files(self):
        r = subprocess.run(['git', '--git-dir', str(self.remote), 'ls-tree', '-r', '--name-only', 'transfer/unit-test'],
                           capture_output=True, text=True, check=True)
        return set(r.stdout.split())

    def commits(self):
        r = subprocess.run(['git', '--git-dir', str(self.remote), 'rev-list', '--count', 'transfer/unit-test'],
                           capture_output=True, text=True, check=True)
        return int(r.stdout)

    def test_publishes_records_incrementally_and_leaves_cache_and_models(self):
        r = self.publish('--once')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.remote_files(), {'README.md', 'match-a/manifest.json', 'match-a/state.json', 'match-a/corpus.jsonl',
                                               'match-a/plan.json', 'match-a/episodes/000000.json.gz', 'match-a/receipts/000000.json'})
        self.assertEqual(self.publish('--once').returncode, 0)          # nothing new: no second commit
        self.assertEqual(self.commits(), 1)
        self.board(1)
        self.assertEqual(self.publish('--once').returncode, 0)
        self.assertEqual(self.commits(), 2)
        self.assertIn('match-a/episodes/000001.json.gz', self.remote_files())
        state = subprocess.run(['git', '--git-dir', str(self.remote), 'show', 'transfer/unit-test:match-a/state.json'],
                               capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(state)['completed'], 2)

    def test_loop_exits_once_a_stopped_run_is_fully_published(self):
        (self.run_dir / 'STOP').write_text('')
        r = self.publish('--every', '0.2')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('fully published', r.stdout)
        self.assertEqual(self.commits(), 1)

    def test_refuses_a_branch_that_is_not_a_transfer_branch(self):
        r = self.publish('--once', branch='arena-gen6-codex-feed')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('transfer/', r.stderr)


if __name__ == '__main__':
    unittest.main()
