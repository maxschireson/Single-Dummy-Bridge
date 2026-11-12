import random
import unittest
from dataclasses import replace
from bridge_harness.core import symbol
from bridge_harness.corpus import generate
from bridge_harness.players import Decision
from bridge_harness.fork_audit import ForkBudget, collect_board, audited_gain


class ToyPlayer:
    def __init__(self,lie=0):self.lie=lie
    def choose(self,o,rng):
        choices=sorted(o.legal);chosen=choices[rng.randrange(len(choices))]
        return Decision(chosen,dict(reference_card=symbol(choices[-1]),expected_gain_imps=self.lie))


class ForkTests(unittest.TestCase):
    def test_reward_perspective_and_imp_boundaries(self):
        self.assertEqual(audited_gain(420,170,0),6)
        self.assertEqual(audited_gain(420,170,1),-6)
        self.assertEqual(audited_gain(-50,420,2),-10)

    def test_predictions_cannot_change_audit_coin_or_play(self):
        b=next(generate(1,173));outputs=[]
        for lie in (-999,999):
            budget=ForkBudget(probability=.5,multiplier=1000,max_depth=1,max_forks=64)
            outputs.append(collect_board(b,{'candidate':ToyPlayer(lie)},['candidate']*4,456,budget,{}))
        a,z=outputs
        self.assertEqual([v['card'] for v in a['tables'][0]['actions']],[v['card'] for v in z['tables'][0]['actions']])
        self.assertEqual([(v['ply'],v['gain_imps']) for v in a['audits']],[(v['ply'],v['gain_imps']) for v in z['audits']])
        for event in a['audits']:
            t=a['tables'][event['candidate_table']];u=a['tables'][event['reference_table']];p=event['ply']
            self.assertEqual([v['card'] for v in t['actions'][:p]],[v['card'] for v in u['actions'][:p]])
            self.assertTrue(t['actions'][p]['committed_before_audit'])
            self.assertEqual(event['gain_imps'],audited_gain(t['ns_score'],u['ns_score'],event['actor']))

    def test_depth_and_shared_budget(self):
        b=next(generate(1,174));budget=ForkBudget(probability=1,multiplier=1000,max_depth=2,max_forks=8)
        r=collect_board(b,{'candidate':ToyPlayer()},['candidate']*4,457,budget,{})
        self.assertLessEqual(len(r['tables']),9)
        self.assertTrue(all(t['depth']<=2 for t in r['tables']))
        self.assertAlmostEqual(budget.branch_cpu,sum(t['cpu_seconds'] for t in r['tables'][1:]))
        self.assertFalse(ForkBudget(base_cpu=1,branch_cpu=2).admit(.01))
        self.assertFalse(ForkBudget(base_cpu=1).admit(3))


if __name__=='__main__':unittest.main()
