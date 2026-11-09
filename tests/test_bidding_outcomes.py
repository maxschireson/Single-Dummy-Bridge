import copy
from dataclasses import replace
import unittest
import numpy as np

from bridge_harness.bidding_env import deal_key, make_board
from bridge_harness.bidding_outcomes import prepare, advantage_weights, crossfit_baseline
from bridge_harness.core import Contract


def record(split='train', score=420, tricks=10):
    b=replace(make_board(602,0,'train'),dealer=0,vulnerability='None',
              contract=Contract(4,'S',0),auction=('4S','PASS','PASS','PASS'))
    return dict(board=b.to_dict(),ns_score=score,declarer_tricks=tricks,
                family=deal_key(b.hands,True),split=split,source='current',
                table_kind='unbranched-root',fork_outcomes_excluded=True,trajectory_identity='table-1')


class OutcomeTests(unittest.TestCase):
    def test_orientation_equal_side_weight_and_duplicate_dedup(self):
        r=record();examples,counts=prepare([r,copy.deepcopy(r)],{'current'})
        self.assertEqual(counts['actual_tables'],1)
        self.assertEqual(counts['duplicate_tables'],1)
        self.assertEqual([e['reward'] for e in examples],[.9,-.9,.9,-.9])
        for side in (0,1):self.assertAlmostEqual(sum(e['weight'] for e in examples if e['side']==side),.5)

    def test_scores_are_verified_and_forks_rejected(self):
        r=record(score=430)
        with self.assertRaisesRegex(ValueError,'score'):prepare([r],{'current'})
        r=record();r['table_kind']='fork'
        with self.assertRaisesRegex(ValueError,'unbranched'):prepare([r],{'current'})

    def test_split_conflict_detected_even_for_duplicate(self):
        r=record();v=record('validation')
        with self.assertRaisesRegex(ValueError,'crosses'):prepare([r,v],{'current'})

    def test_target_changes_never_change_inputs(self):
        good,_=prepare([record()],{'current'})
        bad,_=prepare([record(score=-50,tricks=9)],{'current'})
        self.assertNotEqual(good[0]['reward'],bad[0]['reward'])
        for a,b in zip(good,bad):
            np.testing.assert_array_equal(a['x'],b['x'])
            np.testing.assert_array_equal(a['mask'],b['mask'])

    def test_repeated_tables_average_instead_of_multiply_weight(self):
        a=record();b=record(score=-50,tricks=9);b['trajectory_identity']='table-2'
        examples,counts=prepare([a,b],{'current'})
        self.assertEqual(counts['distinct_auctions'],1)
        self.assertAlmostEqual(examples[0]['reward'],.35)
        self.assertAlmostEqual(sum(e['weight'] for e in examples),1)

    def test_crossfit_excludes_own_fold_and_validation_labels(self):
        rng=np.random.default_rng(3);n=30
        features=rng.normal(size=(n,3))
        family=np.array([f'{0:08x}{i:08x}'+'0'*48 for i in range(n)])
        data=dict(family=family,split=np.array(['train']*25+['validation']*5),
                  reward=rng.normal(size=n),weight=np.ones(n))
        first,_,fold=crossfit_baseline(features,data)
        modified={**data,'reward':data['reward'].copy()}
        modified['reward'][25:]+=1000
        second,_,_=crossfit_baseline(features,modified)
        np.testing.assert_allclose(first,second)
        modified['reward'][np.flatnonzero((fold==0)&(data['split']=='train'))]+=1000
        third,_,_=crossfit_baseline(features,modified)
        np.testing.assert_allclose(first[(fold==0)&(data['split']=='train')],
                                   third[(fold==0)&(data['split']=='train')])

    def test_better_actual_return_gets_more_weight(self):
        w=advantage_weights(np.array([-100.,-.2,0.,.2,100.]),np.zeros(5))
        self.assertTrue(np.all(np.diff(w)>0))
        self.assertEqual(w[0],.25);self.assertEqual(w[-1],4.)


if __name__=='__main__':unittest.main()
