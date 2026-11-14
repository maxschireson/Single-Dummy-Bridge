import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('standing', Path(__file__).resolve().parents[1] / 'ops/stu_standing.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


class StandingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.w = Path(self.tmp.name)
        self.r = self.w / 'standing.json'
        self.config = dict(box=1, pair='stu4c-psta~stu4c-pstb', seed=9001, workers=2, deals=10, options=['--episodes'], name_prefix='sp')
        self.r.write_text(json.dumps(self.config))
        self.runner = self.w / 'runner.sh'
        self.runner.write_text('printf "%s\\n" "$*" >> "$(dirname "$0")/calls"\n')

    def state(self):
        return json.loads((self.w / 'standing-state.json').read_text())

    def test_progress_and_restart(self):
        s.run(self.r, self.w, self.runner, max_jobs=2)
        self.assertEqual(self.state()['next'], s.ORIGIN + 20)
        s.run(self.r, self.w, self.runner, max_jobs=1)
        lines = (self.w / 'calls').read_text().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertIn(str(s.ORIGIN + 20), lines[-1])

    def test_disjoint_bands(self):
        for box in (1, 2, 6, 7):
            d = self.w / str(box)
            d.mkdir()
            r = d / 'standing.json'
            r.write_text(json.dumps(dict(self.config, box=box)))
            s.run(r, d, self.runner, max_jobs=1)
            self.assertEqual(json.loads((d / 'standing-state.json').read_text())['first'], s.ORIGIN + (box - 1) * s.STRIDE)

    def test_failures_never_retry(self):
        self.runner.write_text('exit 3\n')
        self.assertEqual(s.run(self.r, self.w, self.runner, max_jobs=1), 3)
        self.assertEqual(self.state()['status'], 'failed')
        with self.assertRaises(RuntimeError):
            s.run(self.r, self.w, self.runner, max_jobs=1)

    def test_crash_after_reservation_never_reuses(self):
        with patch.object(s.subprocess, 'run', side_effect=OSError('crash')):
            with self.assertRaises(OSError):
                s.run(self.r, self.w, self.runner, max_jobs=1)
        self.assertEqual(self.state()['status'], 'reserved')
        with self.assertRaises(RuntimeError):
            s.run(self.r, self.w, self.runner, max_jobs=1)

    def test_stop_and_lock(self):
        (self.w / 'FALLBACK_STOP').touch()
        self.assertEqual(s.run(self.r, self.w, self.runner, max_jobs=1), 0)
        self.assertFalse((self.w / 'calls').exists())
        (self.w / 'FALLBACK_STOP').unlink()
        with s.locked(self.w / 'standing.lock'):
            with self.assertRaises(BlockingIOError):
                s.run(self.r, self.w, self.runner, max_jobs=1)

    def test_reject_overrides_and_seed(self):
        for changes in [dict(seed=131), dict(options=['--seed', '131']), dict(box=0), dict(workers=True), dict(options=['--out=/tmp/wrong'])]:
            self.r.write_text(json.dumps(dict(self.config, **changes)))
            with self.assertRaises(ValueError):
                s.recipe(self.r)

    def test_existing_run_refused(self):
        (self.w / 'runs' / f'sp-fb1-{s.ORIGIN}').mkdir(parents=True)
        with self.assertRaises(RuntimeError):
            s.run(self.r, self.w, self.runner, max_jobs=1)

    def test_heartbeat_boundary_recovery_and_reboot(self):
        a = s.heartbeat_value({}, 0, 100, 'boot')
        self.assertFalse(s.heartbeat_value(a, 0, 1000, 'boot')['idle_over_15m'])
        self.assertTrue(s.heartbeat_value(a, 0, 1001, 'boot')['idle_over_15m'])
        for active, boot in [(1, 'boot'), (None, 'boot'), (0, 'new-boot')]:
            self.assertFalse(s.heartbeat_value(a, active, 1001, boot)['idle_over_15m'])

    def test_band_exhaustion_and_box_change(self):
        state = dict(box=1, next=s.ORIGIN+s.STRIDE-1, status='complete')
        (self.w/'standing-state.json').write_text(json.dumps(state))
        with self.assertRaises(RuntimeError):
            s.run(self.r, self.w, self.runner, max_jobs=1)
        self.r.write_text(json.dumps(dict(self.config, box=2)))
        with self.assertRaises(ValueError):
            s.run(self.r, self.w, self.runner, max_jobs=1)

    def test_chain_handoff_and_disabled_default(self):
        repo = Path(__file__).resolve().parents[1]
        source = self.w/'source'
        here = source/'training/rollout-loop-20261113'
        here.mkdir(parents=True)
        (source/'ops').mkdir()
        shutil.copy(repo/'ops/stu_standing.py', source/'ops/stu_standing.py')
        # Reconstruct the tiny original so the shipped integration patch is exercised.
        original = '#!/usr/bin/env bash\n'
        patch_text = (repo/'docs/stu-efficiency/P04-chain-pub.patch').read_text()
        chain_patch = patch_text.split('--- a/training/rollout-loop-20261113/pub.sh')[0]
        # Added block follows the final unchanged line of chain.sh; the tested integration is this exact block.
        additions = '\n'.join(line[1:] for line in chain_patch.splitlines() if line.startswith('+') and not line.startswith('+++'))
        chain = here/'chain.sh'
        chain.write_text('set -eu\nHERE=$(cd "$(dirname "$0")" && pwd)\nwhile read -r line; do bash "$HERE/${2:-run.sh}" $line; done < "$1"\n' + additions.replace('$HOME/work/loop',str(self.w)))
        (self.w/'venv/bin').mkdir(parents=True)
        (self.w/'venv/bin/python').symlink_to(sys.executable)
        runner = here/'run.sh'
        runner.write_text('printf "%s\\n" "$*" >> "'+str(self.w/'calls')+'"\ncase "$1" in *-fb*) touch "'+str(self.w/'FALLBACK_STOP')+'";; esac\n')
        jobs=self.w/'jobs.txt';jobs.write_text('queued A~B 9001 0 1 1\n')
        self.r.unlink()  # no configured recipe: only queued job
        subprocess.run(['bash',str(chain),str(jobs)],check=True)
        self.assertEqual(len((self.w/'calls').read_text().splitlines()),1)
        self.r.write_text(json.dumps(self.config))
        subprocess.run(['bash',str(chain),str(jobs)],check=True)
        lines=(self.w/'calls').read_text().splitlines()
        self.assertEqual(len(lines),3)
        self.assertTrue(lines[-1].startswith('sp-fb1-'))

    def test_pair_rotation_persists(self):
        cfg=dict(self.config);del cfg['pair'];cfg['pairs']=['A~B','C~D','E~F']
        self.r.write_text(json.dumps(cfg))
        s.run(self.r,self.w,self.runner,max_jobs=2)
        s.run(self.r,self.w,self.runner,max_jobs=2)
        pairs=[line.split()[1] for line in (self.w/'calls').read_text().splitlines()]
        self.assertEqual(pairs,['A~B','C~D','E~F','A~B'])
        for bad in [dict(cfg,pair='A~B'),dict(cfg,pairs=[]),dict(cfg,pairs=['invalid'])]:
            self.r.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):s.recipe(self.r)

    def test_busy_sources(self):
        for path in ['/src/scripts/train_rollout_net.py','/src/bench/seat_variants.py','scripts/stu_rollout_experiments/worker.py']:
            self.assertTrue(s.busy_token(path.encode()))
        self.assertFalse(s.busy_token(b'/src/other/seat_variants.py'))
        (self.w/'BUSY').touch()
        self.assertEqual(s.busy_count(self.w),(1,'operator BUSY marker'))
        (self.w/'BUSY').unlink()
        with patch.object(s,'match_count',return_value=0):
            with patch.object(s.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'active\n','')):
                self.assertEqual(s.busy_count(self.w),(1,'perf-ab.service'))
            with patch.object(s.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'inactive\n','')):
                self.assertEqual(s.busy_count(self.w)[0],0)
            with patch.object(s.subprocess,'run',side_effect=OSError('no systemd')):
                self.assertIsNone(s.busy_count(self.w)[0])

    def test_process_match_is_exact(self):
        p = self.w / '123'
        p.mkdir()
        (p / 'cmdline').write_bytes(b'python\0/src/scripts/x8_match.py\0--seed\09001\0')
        self.assertEqual(s.match_count(self.w), 1)
        (p / 'cmdline').write_bytes(b'python\0x8_match.py.backup\0')
        self.assertEqual(s.match_count(self.w), 0)


if __name__ == '__main__':
    unittest.main()
