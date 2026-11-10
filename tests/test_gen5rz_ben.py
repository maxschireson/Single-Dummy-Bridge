from copy import deepcopy
from fractions import Fraction
import unittest
from unittest.mock import patch
from bridge_harness.corpus import generate
from bridge_harness.gen5_arena import run_board
from ops.gen5_runtime import validate
from ops.prepare_gen5rz import make_bots as initial_bots,load_plan as initial_plan
from ops.prepare_gen5rz_ben import make_bots,load_plan,PAIR_WEIGHTS
from tests.test_gen5rz import old_bots
from tests.test_gen5r import Toy

class Gen5RZBenTests(unittest.TestCase):
    def test_only_ben_actor_changes_and_zero_margin_both_efforts(self):
        old=initial_bots(dict(bots=old_bots()),initial_plan());bots=make_bots(dict(bots=old),load_plan())
        for key,spec in old.items():self.assertEqual(bots[key],spec)
        a=deepcopy(bots['5RZ192']);b=deepcopy(bots['5R192'])
        self.assertEqual(a['samples'],192);self.assertEqual(a['layout_reduction']['large_pool'],768);self.assertEqual(a['near_tie'],0)
        self.assertEqual(bots['5RZ32']['near_tie'],0);a.pop('policy_role')
        for key in ['id','identity','near_tie']:a.pop(key);b.pop(key)
        self.assertEqual(a,b)
        plan=load_plan();total=sum(PAIR_WEIGHTS.values());self.assertEqual(total,370)
        self.assertEqual(Fraction(PAIR_WEIGHTS['5RZ32~5R32'],total),Fraction(3,10));self.assertEqual(Fraction(PAIR_WEIGHTS['5R32~5-32'],total),Fraction(1,5))
        self.assertEqual(PAIR_WEIGHTS['5RZ192~ben'],10);self.assertNotIn('5R192~ben',PAIR_WEIGHTS)
        for pair,n in initial_plan()['pair_weights'].items():self.assertEqual(PAIR_WEIGHTS['5RZ192~ben' if pair=='5R192~ben' else pair],n)

    def test_ben_runs_z192_and_every_other_pair_is_preserved(self):
        plan=load_plan();bots=make_bots(dict(bots=initial_bots(dict(bots=old_bots()),initial_plan())),plan);board=next(generate(1,429))
        for pair in PAIR_WEIGHTS:
            used=[]
            def factory(spec,root,reference=None):used.append((spec['id'],spec['samples']));return Toy(spec,root,reference)
            m=dict(identity='fixture',roster=plan['roster'],target=1,seed=11,bots=bots,pair_schedule=[pair],audit_references={'5RZ32':'3','5RZ192':'3','5R32':'3','5R192':'3'},common_bidder='5R32',audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=0),ben_audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=0))
            with patch('bridge_harness.gen5_arena.auction',lambda b,actors:(b,[])):
                r=run_board('.',m,board.to_dict(),0,{key:object() for key in bots},player_factory=factory)
            validate(r,m,0)
            if 'ben' in pair:self.assertEqual(used,[('5RZ192',192),('ben',16)])
            else:self.assertEqual([k for k,_ in used],pair.split('~'))

if __name__=='__main__':unittest.main()
