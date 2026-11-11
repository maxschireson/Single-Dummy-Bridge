import gzip
import json
from pathlib import Path
import tempfile
import unittest
from bridge_harness.fork_audit import GapForks
from bridge_harness.loop_registry import sha
from bridge_harness.training import digest
from ops.report_gen7_capture import clustered,correlation,report
from tests.test_gap_forks import collect


class ReportTests(unittest.TestCase):
    def test_standard_errors_cluster_repeated_deal_rows(self):
        value=clustered([1,1,3,3],['a','a','b','b'])
        self.assertEqual(value,dict(n=4,mean=2,se=1,deals=2))
        self.assertIsNone(clustered([1,2],['a','a'])['se'])
        rows=[dict(table=t,realized=x,estimated=0) for t,x in [('a',1),('a',1),('b',3),('b',3)]]
        self.assertEqual(correlation(rows)['icc'],1)

    def test_real_record_report_is_read_only_and_checks_receipts(self):
        with tempfile.TemporaryDirectory() as d:
            run=Path(d);(run/'receipts').mkdir();(run/'episodes').mkdir()
            _,_,record=collect(gap=GapForks(max_cpu_share=1000))
            m=dict(gap_fork=dict(per_band=2,bands=[.125,.5],max_cpu_share=1.5),bots={'a':{},'b':{}});m['identity']=digest(m)
            (run/'manifest.json').write_text(json.dumps(m))
            ep=run/'episodes/000000.json.gz'
            with gzip.open(ep,'wt') as f:json.dump(dict(family=record['family'],unique_tables={'x':record}),f)
            receipt=dict(index=0,manifest_identity=m['identity'],episode_sha256=sha(ep),completed_epoch=10,pair='a~b',root_games=1)
            (run/'receipts/000000.json').write_text(json.dumps(receipt))
            initial=ep.read_bytes()
            result=report(run,run,threshold=1)
            self.assertEqual(result['status'],'completed');self.assertEqual(result['root_tables'],1)
            self.assertEqual(result['gap_forks'],len(record['gap_forks']))
            self.assertEqual(ep.read_bytes(),initial)
            ep.write_bytes(b'corrupt')
            with self.assertRaises(ValueError):report(run,run,threshold=1)


if __name__=='__main__':unittest.main()
