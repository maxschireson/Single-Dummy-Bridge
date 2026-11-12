import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bridge_harness.corpus import generate
from bridge_harness.gen5_arena import run_board
from bridge_harness.gen6 import Gen6Config
from bridge_harness.selfplay import atomic_json
from ops.prepare_gen6 import load_plan
from ops import export_gen5
from tests.test_gen5 import Toy


PLAN = Path(__file__).resolve().parents[1] / 'configs/round6-cutover.json'


class Gen6CutoverTests(unittest.TestCase):
    def test_requested_mix_budgets_and_launch_gate(self):
        with self.assertRaises(ValueError):
            load_plan(PLAN)
        p = load_plan(PLAN, require_ready=False)
        self.assertEqual(p['common_bidder'], '6-32')
        self.assertEqual(p['pair_weights'], {'6-32~5RZ32': 8, '6-32~6-256': 3,
                         '6-32~ben': 3, '6-32~3': 2, '6-32~2': 2, '6-32~1': 2})
        for key, samples, trick in [('6-32', 32, 7), ('6-256', 256, 6)]:
            bot = p['gen6_bots'][key]
            s = Gen6Config(**bot['gen6'])
            self.assertEqual((bot['samples'], s.mid_from_trick, s.list_from_trick), (samples, 14, trick))
            self.assertEqual((s.lead_source, s.early_source, s.leader_early_source), ('lead_net', 'scorer', ''))

    def test_paired_bidding_uncertainty_and_orientation(self):
        # Total and play vary greatly, but their paired difference is constant.
        rows = [dict(pair='6-32~3', imps=-10, own_imps=-7, different_bidding=True),
                dict(pair='6-32~3', imps=10, own_imps=13, different_bidding=True)]
        old = export_gen5.PAIRS
        export_gen5.PAIRS = ['6-32~3']
        try:
            groups = export_gen5.difference_views(rows)['0']['groups']['6-32~3']
        finally:
            export_gen5.PAIRS = old
        self.assertEqual(groups['bidding']['mean'], 3)
        self.assertEqual(groups['bidding']['se'], 0)
        self.assertEqual(groups['play']['mean'], 0)
        self.assertEqual(groups['total']['mean'], 3)
        self.assertEqual(groups['different_bidding'], 2)
        self.assertEqual(export_gen5.gen6_differences(dict(imps=-5, own_imps=-5)),
                         dict(bidding=0, play=-5, total=-5))

    def test_export_and_cached_reexport_keep_gen6_provenance_and_differences(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'run';out=Path(tmp)/'out';root.mkdir()
            m=dict(identity='test6',variant='6',roster=['6-32','3'],target=1,seed=11,
                   labels={'6-32':'Gen 6 fast (32)','3':'Gen 3'},order=['6-32','3'],
                   bots={k:dict(id=k,identity=k,artifact_sha256={}) for k in ('6-32','3')},
                   pair_weights={'6-32~3':1},pair_schedule=['6-32~3'],audit_references={'6-32':'3'},common_bidder='6-32',
                   audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=0),
                   ben_audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=0),
                   created_epoch=0,title='Gen 6',interpretation='Gen6 auction comparison',model_note='Gen6 engine')
            board=next(generate(1,341))
            with patch('bridge_harness.gen5_arena.auction',lambda b,actors:(b,[])):
                r=run_board(root,m,board.to_dict(),0,{k:object() for k in m['bots']},player_factory=Toy)
            r['decision_timing']={}
            atomic_json(root/'manifest.json',m)
            atomic_json(root/'heartbeat.json',dict(epoch=0,workers=0))
            atomic_json(root/'episodes/000000.json.gz',r,compressed=True)
            for _ in range(2):
                export_gen5.export(root,out)
                data=json.loads((out/'arena/data.json').read_text())
                self.assertEqual(data['model_note'],'Gen6 engine')
                self.assertEqual(data['interpretation'],'Gen6 auction comparison')
                group=data['difference_views']['0']['groups']['6-32~3']
                self.assertEqual(group['bidding']['total'],0)
                self.assertEqual(group['play']['total'],r['regimes']['common']['imps'])
                full=json.loads((out/'arena/replays/data/test6/boards-00000.json').read_text())['0']
                self.assertEqual(full['differences']['total'],r['regimes']['native']['imps'])
                self.assertEqual(full['conditions']['common']['label'],'Common Gen6 bidder')


if __name__ == '__main__':
    unittest.main()
