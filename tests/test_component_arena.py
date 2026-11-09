import unittest
from copy import deepcopy
from scripts.prepare_component_arena import component_bots
from bridge_harness.arena_pairs import pair_id,pair_members
from bridge_harness.v4_arena import run_board
from bridge_harness.bidding_env import make_board
from scripts.export_supplemental_feed import view
from tests.test_v4_arena import PassBidder,Player,ArenaTests

class ComponentTests(unittest.TestCase):
    def test_component_identity(self):
        bots={k:dict(id='gen'+k,label='Gen '+k,identity=k,belief=k+'belief',policy=k+'policy',
            bidding=k+'bidder',samples=32,belief_kind='public',
            artifact_sha256={x:k+x for x in ['policy','belief','bidding']}) for k in ['3','4']}
        original=deepcopy(bots);out=component_bots(bots)
        self.assertEqual(bots,original)
        for name,changed,unchanged in [('4p','policy','belief'),('4b','belief','policy')]:
            self.assertEqual(out[name][changed],bots['4'][changed])
            self.assertEqual(out[name][unchanged],bots['3'][unchanged])
            self.assertEqual(out[name]['bidding'],bots['3']['bidding'])
            self.assertEqual(out[name]['artifact_sha256'][changed],bots['4']['artifact_sha256'][changed])
            self.assertNotEqual(out[name]['identity'],bots['3']['identity'])
    def test_pairs_and_export(self):
        self.assertEqual(pair_members(pair_id('4p','3')),('4p','3'))
        self.assertEqual(pair_id('4','3'),'43')
        rows=[dict(pair='4p~3',imps=3,own_imps=-2)]
        v=view(rows,pairs=['4p~3'],labels={'4p':'Gen 4p','3':'Gen 3'})
        self.assertEqual(v['matrix']['3']['4p']['total'],-3)
        self.assertEqual(view(rows,own=True,pairs=['4p~3'],labels={'4p':'Gen 4p','3':'Gen 3'})['groups']['4p~3']['total'],-2)
    def test_multichar_schedule(self):
        m=ArenaTests().manifest();m['bots']['4p']=deepcopy(m['bots']['4']);m['bots']['4p']['identity']='4p'
        m['roster']=['4','4p','3'];m.update(pair_schedule=[['4p','3']],audit_references={'4p':'3'},common_bidder='4')
        r=run_board('.',m,make_board(45,1,'train').to_dict(),0,{k:PassBidder() for k in m['roster']},player_factory=Player)
        self.assertEqual(r['pair'],'4p~3');self.assertEqual(r['opponent'],'3')
        self.assertEqual(r['regimes']['common']['tables'],r['regimes']['native']['tables'])

if __name__=='__main__':unittest.main()
