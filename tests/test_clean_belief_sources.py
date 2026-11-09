import unittest
from scripts.freeze_clean_belief_sources import clean_local

class CleanSourcesTest(unittest.TestCase):
    def test_bad_policy_on_either_partnership_is_excluded(self):
        for a,b in [('4','3'),('3','4p'),('4b','4p'),('4','4')]:
            self.assertFalse(clean_local(dict(candidate=a,opponent=b)))
    def test_belief_upgrade_is_retained(self):
        self.assertTrue(clean_local(dict(candidate='4b',opponent='3',versions={'4':'unused'})))
    def test_missing_provenance_fails_closed(self):
        self.assertFalse(clean_local({}))
        self.assertFalse(clean_local(dict(candidate='4b')))

if __name__=='__main__':unittest.main()
