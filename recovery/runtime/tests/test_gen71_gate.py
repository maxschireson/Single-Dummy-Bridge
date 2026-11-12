import unittest
from ops.check_gen71_gate import gate
class Gate(unittest.TestCase):
    def test_minimum_and_positive_interval_both_required(self):
        self.assertFalse(gate([1]*999)['eligible'])
        self.assertTrue(gate([1]*1000)['eligible'])
        self.assertFalse(gate([1,-1]*500)['eligible'])
        self.assertFalse(gate([-1]*1000)['eligible'])
        self.assertFalse(gate([])['eligible'])
