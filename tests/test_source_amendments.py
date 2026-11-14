"""A run goes on after a harness change only when its folder lists the new source in source-amendments.json."""
import json
from pathlib import Path
import tempfile
import unittest

from bridge_harness.mixed_arena import AMENDMENTS, check_source

PIN, NEW, OTHER = 'a' * 64, 'b' * 64, 'c' * 64


class SourceAmendmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.m = {'source_sha256': PIN}

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, value):
        (self.root / AMENDMENTS).write_text(json.dumps(value))

    def test_the_pinned_source_needs_nothing(self):
        self.assertIsNone(check_source(self.root, self.m, PIN))

    def test_a_changed_source_is_refused_without_the_file_and_named(self):
        with self.assertRaisesRegex(ValueError, 'Pinned generation source changed: source ' + NEW):
            check_source(self.root, self.m, NEW)

    def test_a_listed_source_is_accepted(self):
        self.write([{'source_sha256': NEW, 'reason': 'DDS cache syncs NORMAL', 'commit': 'abc1234'}])
        self.assertEqual(check_source(self.root, self.m, NEW)['commit'], 'abc1234')

    def test_a_source_not_listed_is_refused(self):
        self.write([{'source_sha256': NEW, 'reason': 'DDS cache syncs NORMAL'}])
        with self.assertRaisesRegex(ValueError, 'Pinned generation source changed'):
            check_source(self.root, self.m, OTHER)

    def test_entries_need_a_hash_and_a_reason(self):
        for bad in ({'source_sha256': NEW}, [{'source_sha256': 'xyz', 'reason': 'r'}], [{'source_sha256': NEW, 'reason': ''}]):
            self.write(bad)
            with self.assertRaisesRegex(ValueError, 'list of entries'):
                check_source(self.root, self.m, NEW)


if __name__ == '__main__':
    unittest.main()
