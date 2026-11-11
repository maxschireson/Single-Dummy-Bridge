import gzip,json,tempfile,time
from pathlib import Path
import unittest
from unittest.mock import patch
from bridge_harness.corpus import generate
from bridge_harness.gen5_arena import run_board
from bridge_harness.selfplay import atomic_json
from ops.gen5_runtime import validate,receipt
from ops.export_gen5 import export
from tests.test_gen5 import Toy


class FastSelfplayTests(unittest.TestCase):
    def test_selfplay_is_one_replayable_training_table_with_null_comparison(self):
        board=next(generate(1,341))
        m=dict(identity='testself',variant='6',roster=['6-32','ben'],target=1,seed=11,
            bots={k:dict(id=k,identity=k,artifact_sha256={}) for k in ('6-32','3','ben')},
            pair_weights={'6-32~6-32':37,'6-32~ben':3},pair_schedule=['6-32~6-32'],audit_references={'6-32':'3'},common_bidder='6-32',
            audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=0),ben_audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=0),
            labels={'6-32':'Gen6fast','ben':'BEN16','3':'Reference only'},order=['6-32','ben'],created_epoch=time.time(),interpretation='Selfplay',model_note='Same Gen6 fast')
        with patch('bridge_harness.gen5_arena.auction',lambda b,actors:(b,[])):
            r=run_board('.',m,board.to_dict(),0,{k:object() for k in m['bots']},player_factory=Toy)
        validate(r,m,0);self.assertEqual(set(r['regimes']),{'self'});self.assertEqual(len(r['unique_tables']),1)
        self.assertIsNone(r['regimes']['self']['imps']);self.assertEqual(next(iter(r['unique_tables'].values()))['assignments'],['candidate']*4)
        r['decision_timing']={}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'run';out=Path(tmp)/'out';root.mkdir();p=root/'episodes/000000.json.gz';atomic_json(p,r,compressed=True)
            got=receipt(r,p);self.assertIsNone(got['imps']);self.assertIsNone(got['own_imps'])
            atomic_json(root/'manifest.json',m);atomic_json(root/'heartbeat.json',dict(epoch=0,workers=0))
            export(root,out);data=json.loads((out/'arena/data.json').read_text());s=data['views']['0']['groups']['6-32~6-32']
            self.assertEqual(s['n'],1);self.assertIsNone(s['mean']);self.assertIsNone(s['total']);self.assertEqual(s['ties'],0)
            self.assertIsNone(data['difference_views']['0']['groups']['6-32~6-32']['bidding']['mean'])
            export(root,out) # cached records keep null results too
        r['regimes']['self']['imps']=0
        with self.assertRaises(ValueError):validate(r,m,0)


if __name__=='__main__':unittest.main()
