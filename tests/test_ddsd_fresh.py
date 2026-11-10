import unittest
from scripts.evaluate_ddsd_fresh import argmax_common,summarize

class FreshEvaluationTests(unittest.TestCase):
    def test_global_best_and_shared_ties(self):
        priority={0:30,1:20,2:10}
        values={0:7.,1:7.125,2:7.0625}
        self.assertEqual(argmax_common(values,priority),1)
        tied={0:7.,1:7.,2:6.9}
        self.assertEqual(argmax_common(tied,priority),1)
        zero_corrected={c:q+0. for c,q in tied.items()}
        self.assertEqual(argmax_common(tied,priority),argmax_common(zero_corrected,priority))

    def test_equal_board_weight_and_direct_imp_comparison(self):
        def audit(v5,corrector,direct):
            return dict(phase=0,distinct_choices=3,any_outcome_difference=True,
                imp_gain={'v5':v5,'corrector':corrector},
                trick_gain={'v5':0,'corrector':0},corrector_vs_v5_imps=direct)
        # One board contributes three audits, the other one. Board weight is equal.
        records=[dict(index=0,passed_out=False,audits=[audit(1,3,1)]*3),
                 dict(index=1,passed_out=False,audits=[audit(3,5,3)])]
        r=summarize(records,2,0)
        self.assertEqual(r['comparisons']['v5_vs_pimc']['imps']['mean'],2)
        self.assertEqual(r['comparisons']['corrector_vs_v5']['imps']['mean'],2)
        self.assertEqual(r['comparisons']['corrector_vs_v5']['imps']['families'],2)

if __name__=='__main__':unittest.main()
