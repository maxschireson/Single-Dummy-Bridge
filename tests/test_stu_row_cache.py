import importlib.util
import tempfile
import unittest
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('cache',Path(__file__).resolve().parents[1]/'scripts/stu_row_cache.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class CacheTests(unittest.TestCase):
    def test_resume_and_invalidation(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);r=d/'record.json.gz';r.write_bytes(b'raw');cache=d/'cache';calls=[]
            def build(eps,out):
                calls.append((eps/'record.json.gz').read_bytes())
                np.savez(out,deal=np.array([0]),family=np.array(['family']),meta=np.zeros((1,11),np.int32),bot_names=np.array(['','A']),deal_split=np.array([0]))
            a=c.cached(r,cache,dict(version=1),build)
            self.assertFalse(a['cache_hit'])
            self.assertTrue(c.cached(r,cache,dict(version=1),build)['cache_hit'])
            self.assertEqual(len(calls),1)
            r.write_bytes(b'changed')
            self.assertFalse(c.cached(r,cache,dict(version=1),build)['cache_hit'])
            self.assertFalse(c.cached(r,cache,dict(version=2),build)['cache_hit'])
            Path(a['path']).write_bytes(b'corrupt')
            r.write_bytes(b'raw')
            self.assertFalse(c.cached(r,cache,dict(version=1),build)['cache_hit'])
            self.assertEqual(len(calls),4)

    def test_failed_build_never_committed(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);r=d/'r';r.write_bytes(b'raw')
            def fail(eps,out):raise RuntimeError('builder failed')
            with self.assertRaises(RuntimeError):c.cached(r,d/'cache',{},fail)
            self.assertEqual(list((d/'cache').glob('*.npz')),[])
            self.assertEqual(list((d/'cache').glob('*.json')),[])

if __name__=='__main__':unittest.main()
