import unittest
from collections import Counter
from pathlib import Path
import json
from bridge_harness.bidding_env import make_board
from bridge_harness.fork_audit import stream
from bridge_harness.v4_arena import run_board
from tests.test_v4_arena import PassBidder,Player,ArenaTests
from scripts.export_supplemental_feed import stats,view

class SupplementTests(unittest.TestCase):
    def test_schedule_and_two_self_rooms(self):
        m=ArenaTests().manifest();m.update(pair_schedule=['44']*8+['43']*4+['42']*2+['41','32'],
            common_bidder='4',two_self_rooms=True,independent_room_seeds=True,audit_references={'4':'3','3':'2'})
        rows=[run_board('.',m,make_board(73,i,'train').to_dict(),i,{k:PassBidder() for k in m['roster']},player_factory=Player) for i in range(16)]
        self.assertEqual(Counter(r['pair'] for r in rows),{'44':8,'43':4,'42':2,'41':1,'32':1})
        for r in rows:
            self.assertEqual(len(r['unique_tables']),2)
            if r['pair']=='44':self.assertIsNone(r['regimes']['self']['imps'])
            else:self.assertEqual(r['regimes']['common']['tables'],r['regimes']['native']['tables'])
    def test_statistical_units_and_reverse_signs(self):
        rows=[dict(pair='43',imps=i,own_imps=-i) for i in [1,2,3]]+[dict(pair='44',imps=None,own_imps=None)]
        result=view(rows)
        self.assertEqual(result['groups']['43']['total'],6)
        self.assertEqual(result['groups']['43']['variance'],1)
        self.assertEqual(result['matrix']['3']['4']['total'],-6)
        self.assertIsNone(result['groups']['44']['total'])
        self.assertEqual(view(rows,window=2)['groups']['43']['total'],5)
        self.assertEqual(view(rows,own=True)['groups']['43']['total'],-6)

if __name__=='__main__':unittest.main()
