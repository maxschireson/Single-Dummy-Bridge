# SPDX-License-Identifier: Apache-2.0
import unittest
from scripts.benchmark_cost_curve import VARIANTS, grade, summarize_rows


class CostCurveTests(unittest.TestCase):
    def test_doubling_units(self):
        self.assertAlmostEqual(grade(.2, 2), .2)
        self.assertAlmostEqual(grade(.2, 4), .1)
        self.assertAlmostEqual(grade(-.2, 2), -.2)
        self.assertIsNone(grade(.2, 1))
        self.assertIsNone(grade(.2, .8))

    def test_cluster_bootstrap_and_ratio_of_totals(self):
        rows=[]
        for i in range(20):
            variants={v:dict(tricks=8,cpu_seconds=1,wall_seconds=2,events={}) for v in VARIANTS}
            variants['alphamu8'].update(tricks=9,cpu_seconds=4)
            rows.append(dict(id=str(i),cohort='related',family=str(i//5),variants=variants))
        r=summarize_rows(rows,replicates=40)['all']['comparisons'][0]
        self.assertEqual(r['clusters'],4)
        self.assertEqual(r['cpu_ratio'],4)
        self.assertEqual(r['tricks_per_board_per_time_doubling'],.5)
        self.assertEqual(r['grade_interval'],[.5,.5])

    def test_bootstrap_preserves_cohort_mix(self):
        rows=[]
        for cohort,n,gain in [('broad',10,1),('related',20,-1)]:
            for i in range(n):
                variants={v:dict(tricks=8,cpu_seconds=1,wall_seconds=2,events={}) for v in VARIANTS}
                variants['alphamu8'].update(tricks=8+gain,cpu_seconds=2)
                rows.append(dict(id=f'{cohort}-{i}',cohort=cohort,
                                 family=str(i//5) if cohort=='related' else None,variants=variants))
        r=summarize_rows(rows,replicates=40)['all']['comparisons'][0]
        self.assertEqual(r['tricks_interval'],[-1/3,-1/3])

if __name__=='__main__': unittest.main()
