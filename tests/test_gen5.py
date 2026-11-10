from collections import Counter
from dataclasses import replace
import unittest
from unittest.mock import patch
from bridge_harness.round5 import load_plan,schedule,members
from bridge_harness.corpus import generate
from bridge_harness.core import Contract
from bridge_harness.players import Decision
from bridge_harness.gen5_arena import run_board
from bridge_harness.fork_audit import stream
from ops.gen5_runtime import validate

class Toy:
    def __init__(self,spec,root,reference=None):self.id=spec['id']
    def choose(self,o,rng):return Decision(sorted(o.legal)[-1 if self.id=='5' else 0],{})
    def close(self):pass

class Gen5Tests(unittest.TestCase):
    def test_requested_allocation(self):
        plan=load_plan();rows=schedule(plan,2000,11);n=Counter(rows)
        self.assertEqual(n,{'5-32~4b':800,'5-32~3':400,'5-32~2':300,'5-32~1':100,'5~ben':100,'5~5-32':300})
        self.assertEqual(plan['historical_v5_samples'],32);self.assertEqual(plan['v5_samples'],192);self.assertEqual(plan['ben']['play_samples'],16)
        self.assertFalse(any({'4','4p'} & set(members(p)) for p in rows))

    def test_matchups_select_the_requested_sample_budgets(self):
        plan=load_plan();board=next(generate(1,342))
        bots={k:dict(id=k,identity=k,samples=192 if k=='5' else 16 if k=='ben' else 32) for k in plan['roster']}
        for pair in plan['pair_weights']:
            used=[]
            def factory(spec,root,reference=None):
                used.append((spec['id'],spec['samples']));return Toy(spec,root,reference)
            m=dict(identity='test',roster=plan['roster'],target=1,seed=11,bots=bots,
                pair_schedule=[pair],audit_references={'5':'3','5-32':'3'},common_bidder='5',
                audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=0),
                ben_audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=0))
            with patch('bridge_harness.gen5_arena.auction',lambda b,actors:(b,[])):
                record=run_board('.',m,board.to_dict(),0,{k:object() for k in bots},player_factory=factory)
            validate(record,m,0)
            opponent=members(pair)[1]
            expected=(192,16) if opponent=='ben' else (192,32) if opponent=='5-32' else (32,32)
            self.assertEqual(tuple(n for _,n in used),expected,pair)

    def test_two_conditions_swapped_seats_and_reuse(self):
        board=next(generate(1,341));plan=load_plan()
        pairs=[p for p,n in plan['pair_weights'].items() for _ in range(n)]
        m=dict(identity='test',roster=plan['roster'],target=20,seed=11,
            bots={k:dict(id=k,identity=k) for k in plan['roster']},pair_schedule=pairs,audit_references={'5':'3','5-32':'3'},common_bidder='5',
            audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=0),ben_audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=0))
        for distinct in (False,True):
            calls=0
            def auction(b,bidders):
                nonlocal calls
                calls+=1
                return (replace(b,contract=Contract(3,'N',0),auction=('3N','PASS','PASS','PASS')) if distinct and calls>1 else b),[]
            with patch('bridge_harness.gen5_arena.auction',auction):
                r=run_board('.',m,board.to_dict(),0,{k:object() for k in m['bots']},player_factory=Toy)
            validate(r,m,0)
            self.assertEqual(set(r['regimes']),{'common','native'})
            self.assertEqual(len(r['unique_tables']),4 if distinct else 2)
            if not distinct:self.assertEqual(r['regimes']['native']['tables'],r['regimes']['common']['tables'])
            r['regimes']['native']['imps']+=1
            with self.assertRaises(ValueError):validate(r,m,0)

if __name__=='__main__':unittest.main()
