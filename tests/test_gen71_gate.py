import unittest
from ops.check_gen71_gate import gate
class Gate(unittest.TestCase):
    def test_minimum_and_positive_interval_both_required(self):
        self.assertFalse(gate([1]*999)['eligible'])
        self.assertTrue(gate([1]*1000)['eligible'])
        self.assertFalse(gate([1,-1]*500)['eligible'])
        self.assertFalse(gate([-1]*1000)['eligible'])
        self.assertFalse(gate([])['eligible'])

    def test_authoritative_families_are_additive_and_pinned(self):
        import json, tempfile, hashlib
        from pathlib import Path
        from ops.check_gen71_gate import training_families
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'artifacts/validation';folder.mkdir(parents=True)
            (folder/'all-training-families.json').write_text(json.dumps(['a','b']))
            new=root/'authoritative.json';new.write_text(json.dumps(['b','c']))
            control=dict(training_family_authority=str(new),training_family_authority_sha256=hashlib.sha256(new.read_bytes()).hexdigest())
            self.assertEqual(training_families(root,control),{'a','b','c'})
            new.write_text('[]')
            with self.assertRaisesRegex(AssertionError,'authority changed'):training_families(root,control)
