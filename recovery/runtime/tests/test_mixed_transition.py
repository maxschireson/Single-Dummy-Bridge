import unittest
from ops.finish_mixed_generation_v2 import successor_plan


class TransitionTests(unittest.TestCase):
    def setUp(self):
        self.m=dict(generation=1,roster=['new','prior','older'],candidate='new',reference='prior')
    def test_failed_updates_do_not_repromote_demoted_bot(self):
        p=successor_plan(self.m,dict(demotion=True,best='prior'),False,False)
        self.assertEqual(p['candidate'],'prior');self.assertEqual(p['roster'],['prior','new','older'])
        self.assertFalse(p['changed']);self.assertNotEqual(p['reference'],p['candidate'])
    def test_inconclusive_unchanged_does_not_duplicate_version(self):
        p=successor_plan(self.m,dict(demotion=None,best='new'),False,False)
        self.assertEqual(p['candidate'],'new');self.assertEqual(p['roster'],self.m['roster'])
    def test_validated_change_gets_trial_despite_parent_demotion(self):
        p=successor_plan(self.m,dict(demotion=True,best='prior'),True,False)
        self.assertEqual(p['candidate'],'g0002-belief-policy');self.assertEqual(p['reference'],'prior')
        self.assertEqual(p['roster'],['g0002-belief-policy','prior','new','older'])


if __name__=='__main__':unittest.main()
