import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bridge_harness.corpus import generate
from bridge_harness.core import symbol
from bridge_harness.players import Decision
from bridge_harness.mixed_arena import mixture, schedule, run_board, validate_pair, compact, summarize


class Toy:
    def __init__(self,spec,root,reference=None):
        self.candidate=spec['id']=='new';self.audit=reference is not None
    def choose(self,o,rng):
        choices=sorted(o.legal);chosen=choices[0] if self.candidate else choices[-1]
        return Decision(chosen,dict(reference_card=symbol(choices[-1])) if self.audit else {})
    def close(self):pass


def manifest(target=4):
    return dict(identity='frozen',candidate='new',reference='old',generation=1,target=target,
        bots={x:dict(id=x,identity=x) for x in ('new','old')},seed=17,
        mixture=mixture(['new','old']),audit=dict(probability=1,multiplier=10000,max_depth=2,max_forks=6),
        demotion_looks=[2,4])


class ArenaTests(unittest.TestCase):
    def test_geometric_tail_and_deterministic_environment(self):
        self.assertEqual([r['weight'] for r in mixture(['a','b','c','d'])],[.5,.25,.125,.125])
        self.assertEqual(mixture(['a']),[dict(version='a',weight=1.)])
        m=manifest()
        self.assertEqual([schedule(m,i) for i in range(100)],[schedule(m,i) for i in range(100)])
        self.assertEqual({schedule(m,i)[1] for i in range(100)},{0,1})

    def test_real_bridge_replay_matched_opponents_and_corruption(self):
        m=manifest();rows=[]
        with patch('bridge_harness.mixed_arena.ArenaPlayer',Toy):
            for i,board in enumerate(generate(4,728)):
                r=run_board('.',m,board.to_dict(),i);validate_pair(r,m,board,i);rows.append(compact(r))
                self.assertEqual(r['focal']['assignments'][1-r['focal_side']], 'environment')
                self.assertEqual(r['control']['assignments'][1-r['focal_side']], 'environment')
                broken=copy.deepcopy(r);broken['imps']+=1
                with self.assertRaises(ValueError):validate_pair(broken,m,board,i)
                broken=copy.deepcopy(r);broken['focal']['tables'][0]['actions'][0]['player']='wrong'
                with self.assertRaises(ValueError):validate_pair(broken,m,board,i)
        s=summarize(rows,m)
        self.assertEqual(s['completed'],4);self.assertTrue(s['complete'])
        self.assertGreater(s['audited_deviations'],0)
        self.assertEqual(s['next_step'],'train-successor')

    def test_inconclusive_boundary_advances_and_negative_demotes(self):
        m=manifest();base=dict(family='f',split='train',opponent='old',audits=0,deviations=0,
            recursive=0,local_imp_sum=0,skips=0,tables=2,base_cpu=1,branch_cpu=0,completed_epoch=0)
        rows=[dict(base,index=i,imps=0) for i in range(4)]
        s=summarize(rows,m);self.assertIsNone(s['demotion']);self.assertEqual(s['best'],'new')
        self.assertEqual(s['next_step'],'train-successor')
        for row in rows:row['imps']=-3
        self.assertEqual(summarize(rows,m)['best'],'old')
        # A later finished job must not trigger a look before the earlier pair arrives.
        self.assertIsNone(summarize(rows[1:],m)['demotion'])


if __name__=='__main__':unittest.main()
