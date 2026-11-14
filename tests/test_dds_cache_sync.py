"""The DDS position cache syncs FULL by default; BRIDGE_DDS_CACHE_SYNC=NORMAL lowers it, anything else is refused."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from bridge_harness.dds_cache import PositionCache


class CacheSyncTests(unittest.TestCase):
    def level(self, value):
        with tempfile.TemporaryDirectory() as tmp:
            lib = Path(tmp) / 'lib.so'
            lib.write_bytes(b'solver')
            env = {k: v for k, v in os.environ.items() if k != 'BRIDGE_DDS_CACHE_SYNC'}
            if value is not None:
                env['BRIDGE_DDS_CACHE_SYNC'] = value
            with mock.patch.dict(os.environ, env, clear=True):
                cache = PositionCache(Path(tmp) / 'c.sqlite', lib)
                try:
                    return cache.db.execute('PRAGMA synchronous').fetchone()[0]
                finally:
                    cache.db.close()

    def test_full_by_default(self):
        self.assertEqual(self.level(None), 2)

    def test_normal_when_asked(self):
        self.assertEqual(self.level('normal'), 1)

    def test_other_values_are_refused(self):
        with self.assertRaises(ValueError):
            self.level('OFF')


if __name__ == '__main__':
    unittest.main()
