from copy import deepcopy
import random
import tempfile
import unittest
from unittest.mock import patch

from bridge_harness.combined_player import CombinedPlayer
from bridge_harness.core import symbol
from bridge_harness.players import Decision, PIMCPlayer
from bridge_harness.improvement import Campaign, initialize
from bridge_harness.loop_registry import freeze_bot
from test_improvement import settings


class CombinedTests(unittest.TestCase):
    def test_exploration_logs_actual_propensities_and_never_leaves_support(self):
        player=CombinedPlayer.__new__(CombinedPlayer);player.exploration=.2
        details=dict(behavior_probabilities={symbol(0):.5,symbol(1):.5},
                     estimates={symbol(0):dict(gap_to_best=0),symbol(1):dict(gap_to_best=.1)})
        class Selector:
            def choose(self,*args):return 0,{0:5.,1:4.}
        player.selector=Selector();seen=set()
        with patch.object(PIMCPlayer,'choose',return_value=Decision(0,details)):
            for seed in range(100):
                result=player.choose(None,random.Random(seed));seen.add(result.card)
                p=result.details['behavior_probabilities']
                self.assertAlmostEqual(p[symbol(0)],.9);self.assertAlmostEqual(p[symbol(1)],.1)
                self.assertEqual(result.details['selected_probability'],p[symbol(result.card)])
                self.assertEqual(result.details['proposal_probabilities'],details['behavior_probabilities'])
        self.assertEqual(seen,{0,1})

    def test_greedy_evaluation_can_never_choose_lower_policy_value(self):
        player=CombinedPlayer.__new__(CombinedPlayer);player.exploration=0.
        class Selector:
            def choose(self,*args):return 1,{0:4.,1:5.}
        player.selector=Selector()
        d=dict(behavior_probabilities={symbol(0):.5,symbol(1):.5},estimates={symbol(1):dict(gap_to_best=.1)})
        with patch.object(PIMCPlayer,'choose',return_value=Decision(0,d)):
            for seed in range(20):self.assertEqual(player.choose(None,random.Random(seed)).card,1)


class ArenaCacheTests(unittest.TestCase):
    def test_screen_excludes_ben_and_confirmation_reuses_parent_ben_across_stages(self):
        with tempfile.TemporaryDirectory() as td:
            s=settings();initialize(td,s);c=Campaign(td)
            try:
                freeze_bot(td,'candidate-a',s['bots']['v1'])
                freeze_bot(td,'candidate-b',s['bots']['v1'])
                with patch.object(c,'pair',wraps=c.pair) as call:
                    result=c.arena(1,4,'candidate-a','v2',4,screen_only=True)
                    self.assertTrue(result['screen_only'])
                    self.assertEqual({x.args[2] for x in call.call_args_list},{'v2'})
                c.arena(1,4,'candidate-a','v2',4)
                cached={p:p.stat().st_mtime_ns for p in c.root.glob('g1/arena-games/*/*.json.gz')}
                c.arena(1,8,'candidate-b','v2',4)
                self.assertTrue(all(p.stat().st_mtime_ns==t for p,t in cached.items()))
                self.assertEqual(c.db.execute("SELECT count(*) FROM deals WHERE role='arena'").fetchone()[0],4)
            finally:c.close()


if __name__=='__main__':unittest.main()
