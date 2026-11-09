import unittest
from unittest.mock import patch
from copy import deepcopy
from bridge_harness.direct_arena import schedule, assignments, run_board, validate_pair, summarize, compact
from bridge_harness.corpus import generate

class Player:
    def __init__(self,*args): pass
    def close(self): pass

class DirectTests(unittest.TestCase):
    def setUp(self):
        self.m=dict(target=21765,seed=27,generation=1,identity='manifest',candidate='a',reference='b',
            direct_versions=dict(A='a',B='b',C='c'),bots={v:dict(identity=v) for v in 'abc'},
            audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=64),legacy_completed=3235,batch_target=25000)
    def test_schedule(self):
        from collections import Counter
        for start in range(0,210,7):
            self.assertEqual(Counter(schedule(self.m,i)[0] for i in range(start,start+7)),dict(AB=4,AC=2,BC=1))
        self.assertEqual([schedule(self.m,i) for i in range(100)], [schedule(self.m,i) for i in range(100)])
        self.assertRaises(ValueError,schedule,self.m,21765)
    def test_assignments(self):
        for pair in ('AB','AC','BC'):
            a=assignments(self.m,pair,0);b=assignments(self.m,pair,1)
            self.assertEqual(len(set(a)),2);self.assertEqual(a[0],a[2]);self.assertEqual(a[1],b[0]);self.assertEqual(a[0],b[1])
    def test_scoring_and_validation(self):
        board=next(generate(1,719))
        def collect(board,players,assignment,seed,budget,versions):
            budget.base_cpu+=1
            # Deliberately different scores by assignment; each table independently replayed in integration test.
            score=420 if assignment[0]=='candidate' else -50
            return dict(board=board.to_dict(),versions=versions,assignments=assignment,
                tables=[dict(ns_score=score,actions=[])],audits=[],budget_skips=[])
        for pair in ('AB','AC','BC'):
            for order in (0,1):
                idx=next(i for i in range(100) if schedule(self.m,i)==(pair,order))
                with patch('bridge_harness.direct_arena.legacy.ArenaPlayer',Player),patch('bridge_harness.direct_arena.collect_board',collect),patch('bridge_harness.direct_arena.replay'):
                    r=run_board('.',self.m,board.to_dict(),idx)
                    self.assertEqual(r['imps'],10 if 'A' in pair else 0)
                    bad=deepcopy(r);bad['imps']+=1
                    self.assertRaises(ValueError,validate_pair,bad,self.m,board,idx)
                    bad=deepcopy(r);bad['control']['assignments']=bad['focal']['assignments']
                    self.assertRaises(ValueError,validate_pair,bad,self.m,board,idx)
                    row=compact(r);state=summarize([row],self.m)
                    self.assertEqual(state['by_pair'][pair]['boards'],1)
                    self.assertIsNone(state['total_imps'])

if __name__=='__main__': unittest.main()
