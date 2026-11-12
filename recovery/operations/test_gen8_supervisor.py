"""Launch regressions for this producer's Gen8 supervisor."""
from copy import deepcopy
from unittest import TestCase, main
from supervise_gen8 import validate_launch


class LaunchTests(TestCase):
    def setUp(self):
        self.m = dict(identity='new', effective_generation=8, systems={'8s-32':'house'}, gen8={'system_scorer':'pinned'},
            collection_control={'gen71_comparison_gate_enabled':False}, pair_weights={'8s-32~71s-32':2,'8c-32~8s-32':1},
            evaluation_exclusions={'families':34092})
        self.p = dict(manifest='new', deals=[{'pair':p} for p in self.m['pair_weights'] for _ in range(2)])
        self.c = dict(manifest='new', gap_forks=1, guess_size=1, best_share=1, replay_score_and_systems_verified=True)

    def test_gen8_launch_accepts_complete_real_capture_proof(self):
        validate_launch(self.m, self.p, self.c)

    def test_retired_gate_cannot_stop_or_start_this_cohort(self):
        for key,value in [('gen71_gate',{'qualified':True}),('collection_control',{'gen71_comparison_gate_enabled':True}),('effective_generation',7.1)]:
            m=deepcopy(self.m);m[key]=value
            with self.assertRaises(AssertionError):validate_launch(m,self.p,self.c)

    def test_every_pair_needs_two_preflight_deals(self):
        p=deepcopy(self.p);p['deals'].pop()
        with self.assertRaises(AssertionError):validate_launch(self.m,p,self.c)

    def test_settings_without_observed_capture_never_launch(self):
        for key in ['gap_forks','guess_size','best_share']:
            c=deepcopy(self.c);c[key]=0
            with self.assertRaises(AssertionError):validate_launch(self.m,self.p,c)

    def test_proof_must_belong_to_current_identity(self):
        c=deepcopy(self.c);c['manifest']='retired'
        with self.assertRaises(AssertionError):validate_launch(self.m,self.p,c)


if __name__ == '__main__':main()
