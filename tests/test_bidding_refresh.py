import unittest
import numpy as np
from bridge_harness.bidding_env import make_board, CALL_ID
from bridge_harness.bidding_refresh import (BAD_POLICY, clean_actors, play_split,
    terminal_scores, expected_imps, auction_pairs, common_support, clustered_summary,digest)
from bridge_harness.core import score, vulnerable, auction_contract, imps


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.b = make_board(181, 0, 'train')

    def test_exclude_either_partnership_and_alias_hash(self):
        manifest = {'bots': {'3': {'policy': 'good', 'artifact_sha256': {'policy': 'abc'}},
                             '4b': {'policy': 'good', 'artifact_sha256': {'policy': 'abc'}},
                             'renamed': {'policy': 'bad', 'artifact_sha256': {'policy': BAD_POLICY}}}}
        self.assertTrue(clean_actors(manifest, {'declarer':'3', 'defender':'4b'}))
        self.assertFalse(clean_actors(manifest, {'declarer':'3', 'defender':'renamed'}))
        self.assertFalse(clean_actors(manifest, {'declarer':'renamed', 'defender':'3'}))
        self.assertFalse(clean_actors(manifest, {'declarer':'unknown'}))

    def test_split_preserves_arena_holdout(self):
        for i in range(100):
            s = play_split(f'{i:08x}'+'0'*56)
            self.assertEqual(s == 'train', i % 5 != 0)

    def test_reuses_tricks_not_score_and_never_other_strain(self):
        b = self.b
        c = auction_contract(b.dealer, ['1N','PASS','PASS','PASS'])
        data = {'outcomes': {f'{c.trump}/{c.declarer}':[8,9]}}
        values, src = terminal_scores(b, ['3N','PASS','PASS','PASS'], data)
        c3 = auction_contract(b.dealer, ['3N','PASS','PASS','PASS'])
        sign = 1 if c3.declarer % 2 == 0 else -1
        self.assertEqual(values, [sign*score(c3,t,vulnerable(b.vulnerability,c3.declarer)) for t in [8,9]])
        self.assertEqual(src, 'clean_play_reused')
        self.assertIsNone(terminal_scores(b,['4S','PASS','PASS','PASS'],data)[0])
        self.assertIsNone(terminal_scores(b,['PASS','1N','PASS','PASS','PASS'],data)[0])
        self.assertEqual(terminal_scores(b,['PASS']*4,data)[0],[0])

    def test_play_takes_precedence_over_dds(self):
        c=auction_contract(self.b.dealer,['1N','PASS','PASS','PASS'])
        d={'outcomes':{f'{c.trump}/{c.declarer}':[7]},'dds':[[13]*4 for _ in range(5)]}
        self.assertEqual(terminal_scores(self.b,['1N','PASS','PASS','PASS'],d)[1], 'clean_play_reused')

    def test_exact_mode_replays_new_level_despite_known_strain(self):
        calls=['1N','PASS','PASS','PASS'];c=auction_contract(self.b.dealer,calls)
        d={'outcomes':{f'{c.trump}/{c.declarer}':[9]},
           'auction_outcomes':{digest(calls):{'tricks':[9]}}}
        self.assertEqual(terminal_scores(self.b,calls,d)[1],'clean_play_exact_auction')
        self.assertIsNone(terminal_scores(self.b,['3N','PASS','PASS','PASS'],d)[0])

    def test_imps_averaged_after_nonlinear_conversion(self):
        self.assertEqual(expected_imps([0,600],[0]), (imps(0)+imps(600))/2)
        self.assertNotEqual(expected_imps([0,600],[0]), imps(300))

    def test_equal_bidders_cancel_with_sparse_scores(self):
        class PassPolicy:
            def predict(self, x, lengths):
                out=np.zeros((len(x),40));out[:,CALL_ID['PASS']]=1
                return out,np.zeros(len(x))
        r={'board':self.b.to_dict(),'family':'one','outcomes':{}}
        rows,decisions=auction_pairs([r],PassPolicy(),PassPolicy(),np.random.default_rng(1))
        self.assertEqual(rows[0]['imps'],0)
        self.assertEqual(decisions,[])

    def test_common_support_and_family_cluster(self):
        a=[{'family':'a','imps':2},{'family':'a','imps':4},{'family':'b','imps':None}]
        b=[{'family':'a','imps':1},{'family':'b','imps':3}]
        self.assertEqual(common_support({'a':a,'b':b}),['a'])
        summary=clustered_summary(a)
        self.assertEqual(summary['families'],1)
        self.assertEqual(summary['mean_imps'],3)

    def test_missing_contract_is_played_when_resolver_supplied(self):
        class NTPolicy:
            def predict(self,x,lengths):
                out=np.zeros((len(x),40));out[:,CALL_ID['1N']]=1;out[:,CALL_ID['PASS']]=.5
                return out,np.zeros(len(x))
        requests=[]
        def resolve(board,calls):
            requests.append(calls)
            return [100],'clean_play_new_or_cached'
        r={'board':self.b.to_dict(),'family':'one','outcomes':{}}
        rows,_=auction_pairs([r],NTPolicy(),NTPolicy(),np.random.default_rng(1),missing_score=resolve)
        self.assertEqual(len(requests),2)
        self.assertEqual(rows[0]['imps'],0)
        self.assertEqual(rows[0]['tables'][0]['reward_source'],'clean_play_new_or_cached')


if __name__ == '__main__':
    unittest.main()
