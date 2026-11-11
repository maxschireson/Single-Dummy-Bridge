import unittest
import numpy as np
from bridge_harness.core import Board,card
from ops.report_gen7_capture import clustered,icc_from_sufficient,touching,effective_touching,phase


class CaptureReportStats(unittest.TestCase):
    def test_cluster_se_keeps_perfectly_correlated_forks_together(self):
        r=[dict(family='a',x=0),dict(family='a',x=0),dict(family='b',x=2),dict(family='b',x=2)]
        s=clustered(r,'x');self.assertEqual(s['mean'],1);self.assertEqual(s['se'],1);self.assertEqual(s['families'],2)
        self.assertIsNone(clustered(r[:2],'x')['se'])
        self.assertEqual(clustered([],'x')['n'],0)

    def test_icc_limits_and_negative_estimate(self):
        self.assertAlmostEqual(icc_from_sufficient([[2,0,0],[2,4,8]]),1)
        self.assertAlmostEqual(icc_from_sufficient([[2,2,4],[2,2,4]]),-1)
        self.assertIsNone(icc_from_sufficient([[2,0,0],[2,0,0]]))

    def test_touching_definitions_and_exclusive_phases(self):
        self.assertTrue(touching('CA','CK'));self.assertFalse(touching('CA','CQ'));self.assertFalse(touching('CA','SA'))
        class Example:
            hands=((card('CA'),card('CQ')),(card('CK'),),(),())
        self.assertFalse(effective_touching(Example(),[],0,0,'CA','CQ'))
        self.assertTrue(effective_touching(Example(),[dict(card='CK')],1,0,'CA','CQ'))
        self.assertEqual([phase(x) for x in [0,1,15,16,31,32,51]],['lead','tricks1-4','tricks1-4','tricks5-8','tricks5-8','tricks9-13','tricks9-13'])


if __name__=='__main__':unittest.main()
