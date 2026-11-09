import unittest
import numpy as np
from scripts.policy_choice_data import family_split, validate_event
from scripts.train_policy_choices import family_summary, metrics


class PolicyChoiceTests(unittest.TestCase):
    def test_old_train_validation_partition_is_preserved(self):
        for index in range(100):
            family = f'{index:08x}' + '0'*56
            self.assertEqual(family_split(family) != 'train', index % 5 == 0)
        self.assertEqual(family_split('00000000'+'0'*56), 'test')
        self.assertEqual(family_split('00000005'+'0'*56), 'validation')

    def test_audit_rejects_reward_and_prefix_corruption(self):
        action = dict(card='C2', committed_before_audit=True, audit_draw=True)
        episode = dict(tables=[dict(ns_score=120, actions=[dict(card='SA'), action]),
                               dict(ns_score=90, actions=[dict(card='SA'), dict(card='C3')])])
        event = dict(candidate_table=0, reference_table=1, ply=1, actor=0,
                     candidate_card='C2', reference_card='C3', gain_imps=1,
                     selection='independent-random-post-commit')
        self.assertEqual(validate_event(episode,event),action)
        with self.assertRaises(ValueError):
            validate_event(episode,dict(event,gain_imps=-1))
        episode['tables'][1]['actions'][0]['card']='SK'
        with self.assertRaises(ValueError):
            validate_event(episode,event)

    def test_family_weighting_and_matched_choice_rewards(self):
        summary = family_summary([4]*20+[-2], np.array(['A']*20+['B']))
        self.assertEqual(summary['mean'],1.)
        data = dict(y=np.array([4.,-2.,0.]),group=np.array(['A','B','C']))
        result = metrics(data,np.array([1.,-1.,0.]),np.ones(3,dtype=bool))
        self.assertEqual(result['regret_to_better_recorded_move']['mean'],0.)
        self.assertEqual(result['decisive_accuracy']['mean'],1.)


if __name__ == '__main__':
    unittest.main()
