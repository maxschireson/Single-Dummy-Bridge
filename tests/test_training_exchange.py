import gzip
import json
from pathlib import Path
import tempfile
import unittest
from ops.training_exchange import pack, restore, snapshot_run, CHUNK_BYTES, digest


class TrainingExchangeTests(unittest.TestCase):
    def test_incremental_roundtrip_and_chunk_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'weights'; source.write_bytes(b'x'*(CHUNK_BYTES+17))
            manifest=pack({'models/weights':source},root/'exchange',{'parent':'frozen'})
            before=set((root/'exchange/chunks').iterdir())
            second=pack({'models/weights':source},root/'exchange',{'parent':'frozen'})
            self.assertEqual(manifest,second)
            self.assertEqual(before,set((root/'exchange/chunks').iterdir()))
            self.assertTrue(all(p.stat().st_size<=CHUNK_BYTES for p in before))
            self.assertEqual(restore(manifest,root/'restored'),{'parent':'frozen'})
            self.assertEqual((root/'restored/models/weights').read_bytes(),source.read_bytes())

    def test_corruption_never_installs_partial_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'data'; source.write_bytes(b'hello')
            manifest=pack({'data':source},root/'exchange',{})
            next((root/'exchange/chunks').iterdir()).write_bytes(b'wrong')
            with self.assertRaises(ValueError): restore(manifest,root/'restored')
            self.assertFalse((root/'restored').exists())

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'data'; source.write_bytes(b'hello')
            with self.assertRaises(ValueError): pack({'../outside':source},root/'exchange',{})

    def test_live_snapshot_only_captures_completed_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); run=root/'run'; (run/'episodes').mkdir(parents=True)
            m=dict(identity='frozen',bots={'candidate':{}},candidate='candidate')
            (run/'manifest.json').write_text(json.dumps(m))
            r=dict(status='ok',manifest_identity='frozen',index=0)
            with gzip.open(run/'episodes/00000.json.gz','wt') as f: json.dump(r,f)
            (run/'episodes/inflight.tmp').write_text('not committed')
            files,meta=snapshot_run(run)
            self.assertEqual(meta['runs'][0]['indices'],[0])
            self.assertEqual(len(files),2)
            self.assertFalse((run/'STOP').exists())


if __name__=='__main__': unittest.main()
