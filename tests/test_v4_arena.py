import unittest
from collections import Counter
import numpy as np
from bridge_harness.v4_arena import schedule, next_roster, run_board
from bridge_harness.bidding_env import make_board

class PassBidder:
    def predict(self,x,lengths):
        p=np.zeros((len(x),40));p[:,2]=1
        return p,np.zeros(len(x))

class Player:
    def __init__(self,*args):pass
    def close(self):pass

class ArenaTests(unittest.TestCase):
    def manifest(self):
        return dict(roster=['4','3','2','1'],target=800,seed=123,identity='test',
                    bots={k:dict(identity=k) for k in ['4','3','2','1']},audit=dict(probability=0,multiplier=1,max_depth=0))
    def test_each_block_has_exact_mixture(self):
        m=self.manifest()
        for at in range(0,800,8):
            self.assertEqual(Counter(schedule(m,i) for i in range(at,at+8)),{'4':4,'3':2,'2':1,'1':1})
    def test_demotion_affects_next_opponent_ranking(self):
        self.assertEqual(next_roster(['4','3','2','1'],'5',True),['5','3','4','2','1'])
        m=self.manifest();m['roster']=next_roster(m['roster'],'5',True)
        self.assertEqual(Counter(schedule(m,i) for i in range(16)),{'5':8,'3':4,'4':2,'2':1,'1':1})
    def test_identical_auctions_reuse_tables_and_passout_needs_no_play(self):
        m=self.manifest();i=next(i for i in range(8) if schedule(m,i)!='4')
        bidders={k:PassBidder() for k in m['roster']}
        r=run_board('.',m,make_board(42,0,'train').to_dict(),i,bidders,player_factory=Player)
        self.assertEqual(len(r['unique_tables']),2)
        self.assertEqual(r['regimes']['common']['tables'],r['regimes']['native']['tables'])
        self.assertEqual(r['regimes']['native']['imps'],0)
    def test_self_play_is_not_reported_as_competitive_tie(self):
        m=self.manifest();i=next(i for i in range(8) if schedule(m,i)=='4')
        r=run_board('.',m,make_board(42,0,'train').to_dict(),i,{k:PassBidder() for k in m['roster']},player_factory=Player)
        self.assertEqual(list(r['regimes']),['self']);self.assertIsNone(r['regimes']['self']['imps'])
        self.assertEqual(len(r['unique_tables']),1)

if __name__=='__main__':unittest.main()
