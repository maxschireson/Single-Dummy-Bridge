import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ops.watch_direct_arena import lock,lock_state,report_views,transient_failures,recover,check,launch_settings

class WatchdogTests(unittest.TestCase):
    def test_check_preserves_recovery_callable(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td)/'run';r.mkdir();pointer=Path(td)/'current.json'
            pointer.write_text(json.dumps(dict(run=str(r))))
            (r/'manifest.json').write_text(json.dumps(dict(protocol='direct-pairs-v1',identity='m',target=10,created_epoch=0)))
            (r/'telemetry-ramp.json').write_text(json.dumps(dict(status='running-verified',launcher='ops/independent_supervisor.py',workers=3)))
            with patch('ops.watch_direct_arena.verify_generation'),patch('ops.watch_direct_arena.receipts',return_value=[]),patch('ops.summarize_arena_health.summarize',return_value={}),patch('ops.watch_direct_arena.launch') as launch:
                launch.return_value.pid=123
                result=check(pointer,2,launcher=launch)
                self.assertEqual(result['action'],'restarted-awaiting-progress')
                self.assertEqual(result['launcher'],'ops/independent_supervisor.py')
                launch.assert_called_once_with(r,3)

    def test_verified_launcher_settings(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            self.assertEqual(launch_settings(p,2),('ops/diagnostic_supervisor.py',2))
            (p/'telemetry-ramp.json').write_text(json.dumps(dict(status='running-verified',launcher='ops/independent_supervisor.py',workers=3)))
            self.assertEqual(launch_settings(p,2),('ops/independent_supervisor.py',3))
            (p/'telemetry-ramp.json').write_text(json.dumps(dict(status='running-verified',launcher='unknown.py',workers=3)))
            self.assertRaises(ValueError,launch_settings,p,2)

    def test_windows(self):
        rows=[dict(pair='AB',completed_epoch=t,imps=v) for t,v in [(1000,3),(1100,-2),(1500,4),(1600,9)]]
        views=report_views(rows,dict(created_epoch=0),1500)
        self.assertEqual(len(views),12)
        self.assertEqual(views['AB-5m']['completed_pairs'],1)
        self.assertEqual(views['AB-5m']['net_imps'],4)
        self.assertEqual(views['AB-15m']['completed_pairs'],3)
        self.assertEqual(views['AB-5m']['pairs_per_hour'],12)
        self.assertFalse(views['AB-60m']['full_window'])
    def test_os_lock(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'lock'
            with lock(p):
                self.assertEqual(lock_state(p),'held')
                with self.assertRaises(BlockingIOError):
                    with lock(p):pass
            self.assertEqual(lock_state(p),'free')
    def test_failure_classification(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'error.json'
            p.write_text(json.dumps(dict(traceback='ValueError: wrong model')))
            self.assertFalse(transient_failures([p]))
            p.write_text(json.dumps(dict(traceback='concurrent.futures.process.BrokenProcessPool: abruptly terminated')))
            self.assertTrue(transient_failures([p]))
    def test_stop_and_live_locks_prevent_launch(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td);m=dict(target=10,identity='m');history=r/'history.json'
            (r/'STOP').touch()
            with patch('ops.watch_direct_arena.launch') as launch:
                self.assertEqual(recover(r,m,2,history,launch)['action'],'intentional-stop');launch.assert_not_called()
            (r/'STOP').unlink()
            with lock(r/'.writer.lock'),patch('ops.watch_direct_arena.launch') as launch:
                with self.assertRaises(BlockingIOError):recover(r,m,2,history,launch)
                launch.assert_not_called()
    def test_retry_preserves_failures_and_stops_after_three(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td);m=dict(target=10,identity='m');hist=r/'attempts.json'
            (r/'failures').mkdir();f=r/'failures'/'000000.json'
            f.write_text(json.dumps(dict(traceback='concurrent.futures.process.BrokenProcessPool: abruptly terminated')))
            with patch('ops.watch_direct_arena.verify_generation'),patch('ops.watch_direct_arena.receipts',return_value=[]),patch('ops.watch_direct_arena.launch') as launch:
                launch.return_value.pid=123
                for _ in range(3):self.assertEqual(recover(r,m,2,hist,launch)['action'],'restarted-awaiting-progress')
                self.assertEqual(recover(r,m,2,hist,launch)['action'],'blocked-repeated-no-progress')
                self.assertEqual(launch.call_count,3)
                self.assertEqual(len(list((r/'failure-history').glob('*/000000.json'))),1)

if __name__=='__main__':unittest.main()
