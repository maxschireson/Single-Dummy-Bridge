import tempfile
from pathlib import Path
from copy import deepcopy
import unittest
from unittest.mock import patch

from bridge_harness.corpus import generate
from bridge_harness.selfplay import atomic_json
from ops.gen4_mix import ALLOCATION, run_board, validate, compact, summarize
from test_gen4_ablation import Toy


class MixTests(unittest.TestCase):
    def test_all_matchups_replay_and_model_assignment(self):
        m = dict(identity='mix', target=len(ALLOCATION), seed=27,
            bots={v:dict(id=v, identity=v) for v in ('4','P','Q','3','2','1')},
            audit=dict(probability=0, multiplier=1, max_depth=0, max_forks=0))
        class Player(Toy):
            def __init__(self, spec, root, reference=None):
                super().__init__(spec, root)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);atomic_json(root/'schedule.json',list(ALLOCATION));rows=[]
            with patch('ops.gen4_mix.ArenaPlayer',Player):
                for i,board in enumerate(generate(len(ALLOCATION),719)):
                    r=run_board(root,m,board.to_dict(),i)
                    validate(r,m,board,i);rows.append(compact(r))
                    self.assertEqual(r['pair'],list(ALLOCATION)[i])
                    if r['pair']=='44':self.assertIsNone(r['imps'])
                    else:self.assertIsInstance(r['imps'],int)
                    bad=deepcopy(r);bad['imps']=999
                    with self.assertRaises(ValueError):validate(bad,m,board,i)
                    bad=deepcopy(r);bad['versions']['P']='wrong'
                    with self.assertRaises(ValueError):validate(bad,m,board,i)
            state=summarize(rows,m)
            self.assertEqual(state['completed'],len(ALLOCATION))
            self.assertEqual(state['contiguous'],len(ALLOCATION))
            self.assertIsNone(state['total_imps'])


if __name__=='__main__':unittest.main()
