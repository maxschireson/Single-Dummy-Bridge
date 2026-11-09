import json,os,tempfile,time,unittest
from pathlib import Path
from ops.diagnostic_supervisor import DiagnosticPool,memory_snapshot,process_snapshot

def crash():os._exit(7)

class DiagnosticsTests(unittest.TestCase):
    def test_resource_snapshot(self):
        self.assertGreater(memory_snapshot()['MemTotal_kb'],0)
        self.assertEqual(process_snapshot(os.getpid())['pid'],os.getpid())
        self.assertIn('cpu_ticks',process_snapshot(os.getpid()))
    def test_records_abrupt_worker_exit(self):
        with tempfile.TemporaryDirectory() as td:
            DiagnosticPool.run=Path(td)
            with self.assertRaises(Exception):
                with DiagnosticPool(max_workers=1) as pool:
                    pool.submit(crash).result()
            events=[json.loads(x) for p in (Path(td)/'diagnostics').glob('*.jsonl') for x in p.read_text().splitlines()]
            self.assertTrue(any(e['event']=='worker-exit' and e['exitcode']==7 for e in events))
            self.assertTrue(any(e['event']=='resources' for e in events))
if __name__=='__main__':unittest.main()
