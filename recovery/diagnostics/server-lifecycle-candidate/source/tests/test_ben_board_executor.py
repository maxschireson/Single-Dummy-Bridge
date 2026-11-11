import json
import os
from pathlib import Path
import signal
import tempfile
import time
import unittest
from concurrent.futures.process import BrokenProcessPool
from ops.ben_board_executor import BenBoardExecutor


def initialize():
    pass


def job(mode):
    if mode == 'error':
        raise ValueError('deliberate test error')
    if mode == 'exit':
        os._exit(7)
    if mode == 'signal':
        os.kill(os.getpid(), signal.SIGKILL)
    if mode == 'wait':
        time.sleep(.5)
    return os.getpid(), bytes(2_000_000)


class TestBenBoardExecutor(unittest.TestCase):
    def test_recycling_large_result_and_exit_status(self):
        with tempfile.TemporaryDirectory() as folder:
            with BenBoardExecutor(folder, initialize, ()) as pool:
                a = pool.submit(job, 'ok').result(timeout=30)
                b = pool.submit(job, 'ok').result(timeout=30)
            self.assertNotEqual(a[0], b[0])
            self.assertEqual(len(a[1]), 2_000_000)
            events = [json.loads(l) for p in Path(folder).rglob('*.jsonl') for l in p.read_text().splitlines()]
            self.assertEqual([e['exitcode'] for e in events if e['event'] == 'worker-exit'], [0, 0])

    def test_failures_preserve_exit_code(self):
        for mode, code in [('error', 1), ('exit', 7), ('signal', -signal.SIGKILL)]:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                with BenBoardExecutor(folder, initialize, ()) as pool:
                    with self.assertRaises(BrokenProcessPool):
                        pool.submit(job, mode).result(timeout=30)
                events = [json.loads(l) for p in Path(folder).rglob('*.jsonl') for l in p.read_text().splitlines()]
                self.assertEqual([e['exitcode'] for e in events if e['event'] == 'worker-exit'], [code])

    def test_serial_lane_and_shutdown(self):
        with tempfile.TemporaryDirectory() as folder:
            pool = BenBoardExecutor(folder, initialize, ())
            future = pool.submit(job, 'wait')
            with self.assertRaises(RuntimeError):
                pool.submit(job, 'ok')
            pool.shutdown()
            self.assertTrue(future.done())
            with self.assertRaises(RuntimeError):
                pool.submit(job, 'ok')


if __name__ == '__main__':
    unittest.main()
