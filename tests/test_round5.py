from collections import Counter
from copy import deepcopy
import unittest
from bridge_harness.round5 import load_plan,validate_plan,schedule,require_ready,members
from bridge_harness.decision_timing import from_game,merge

class Round5Tests(unittest.TestCase):
    def test_roster_and_ben_allocation(self):
        plan=load_plan();rows=schedule(plan,1600,42)
        self.assertEqual(sum('ben' in members(p) for p in rows),80)
        self.assertEqual(rows,schedule(plan,1600,42))
        for pair in rows:
            self.assertFalse(set(members(pair))&{'4','4p'})
            if 'ben' in members(pair):self.assertEqual(set(members(pair)),{'5','ben'})
        self.assertIn('4b',plan['roster'])
        with self.assertRaises(RuntimeError):require_ready(plan)
        bad=deepcopy(plan);bad['pair_weights']['4b~ben']=1
        with self.assertRaises(ValueError):validate_plan(bad)

    def test_timing_ignores_forks_prefixes_and_forced_replays(self):
        def action(ply,seconds,**kw):return dict(ply=ply,player='candidate',seconds=seconds,**kw)
        game=dict(tables=[dict(actions=[action(0,4),action(1,2),action(2,.1,forced=True),
            action(3,100,replayed_prefix=True),action(4,100,counterfactual_forced=True),action(5,100,fixed_opening_lead=True)]),dict(actions=[action(0,999)])])
        a=from_game(game,{'candidate':'Q'});bot=a['by_bot']['4b']
        self.assertEqual(bot['decisions'],3);self.assertAlmostEqual(bot['mean_seconds'],6.1/3)
        self.assertEqual(bot['opening_lead']['mean_seconds'],4)
        self.assertEqual(bot['forced_decisions'],1)
        combined=merge(a,from_game(dict(tables=[dict(actions=[action(0,10)])]),{'candidate':'Q'}))
        self.assertAlmostEqual(combined['by_bot']['4b']['mean_seconds'],16.1/4)
        self.assertEqual(merge()['by_bot'],{})

    def test_missing_timing_is_not_zero_and_invalid_time_rejected(self):
        game=dict(tables=[dict(actions=[dict(ply=0,player='candidate')])])
        self.assertEqual(from_game(game,{'candidate':'ben'})['missing_timing_decisions'],1)
        game['tables'][0]['actions'][0]['seconds']=float('nan')
        with self.assertRaises(ValueError):from_game(game,{'candidate':'ben'})

if __name__=='__main__':unittest.main()
