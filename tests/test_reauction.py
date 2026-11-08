from dataclasses import replace
import copy
import random
import unittest

from bridge_harness.core import Contract, Game, synthetic_auction
from bridge_harness.corpus import generate
from bridge_harness.players import PIMCPlayer
from bridge_harness.runner import run_pair, replay
from bridge_harness.training import digest, examples_from_record
from scripts.reconcile_ben_auctions import classification, relabel
from scripts.train_reauction_belief import auction_tokens, MAX_CALLS


class ReauctionTests(unittest.TestCase):
    def test_auction_encoder_retains_order_and_rejects_truncation(self):
        a=auction_tokens({'auction':['1C','PASS','1H']})
        b=auction_tokens({'auction':['1C','1H','PASS']})
        self.assertFalse((a==b).all())
        self.assertTrue((a[3:]==0).all())
        with self.assertRaises(ValueError):auction_tokens({'auction':['PASS']*(MAX_CALLS+1)})

    @classmethod
    def setUpClass(cls):
        cls.board = next(generate(1, seed=882))
        cfg = dict(mode='selfplay', candidate='pimc', baseline='pimc', common='pimc',
                   samples=4, objective='tricks', near_tie=.125)
        rec = run_pair(cls.board, cfg)
        assert rec['status'] == 'ok', rec
        cls.episode = dict(schema_version=1, episode=0, episode_id='source', record=rec,
                           examples=examples_from_record(rec, 'source'))

    def test_relabel_level_recalculates_scores_and_preserves_splits(self):
        old = copy.deepcopy(self.episode)
        c = replace(self.board.contract, level=7, doubled=1)
        b = replace(self.board, contract=c, auction=synthetic_auction(self.board.dealer,c), auction_source='BEN-test')
        new = relabel(old,b)
        self.assertEqual(old,self.episode)
        self.assertEqual(new['record']['tables'][0]['actions'],old['record']['tables'][0]['actions'])
        replay(new['record'])
        self.assertNotEqual(new['record']['tables'][0]['ns_score'],old['record']['tables'][0]['ns_score'])
        for a,z in zip(old['examples'],new['examples']):
            self.assertEqual(a['belief_target'],z['belief_target'])
            self.assertEqual(a['metadata']['split'],z['metadata']['split'])
            self.assertEqual(tuple(z['observation']['auction']),b.auction)
            self.assertEqual(z['observation']['contract']['level'],7)

    def test_same_strain_different_declarer_rejected(self):
        c=replace(self.board.contract,declarer=(self.board.contract.declarer+2)%4)
        b=replace(self.board,contract=c)
        self.assertEqual(classification(self.episode['record'],b),'replay_required')
        with self.assertRaises(ValueError): relabel(self.episode,b)

    def test_score_objective_rejected(self):
        e=copy.deepcopy(self.episode);e['record']['config']['objective']='score'
        self.assertEqual(classification(e['record'],self.board),'replay_required')

    def test_passout_not_relabelled_as_play(self):
        b=replace(self.board,contract=None,auction=('PASS',)*4)
        self.assertEqual(classification(self.episode['record'],b),'passed_out')

    def test_context_changes_rejected(self):
        with self.assertRaises(ValueError):
            classification(self.episode['record'],replace(self.board,dealer=1))

    def test_play_policy_is_level_and_auction_invariant(self):
        c=replace(self.board.contract,level=7,doubled=2)
        b=replace(self.board,contract=c,auction=synthetic_auction(self.board.dealer,c))
        g,h=Game(self.board),Game(b)
        player=PIMCPlayer(samples=4,objective='tricks',near_tie=.125)
        try:
            while not g.done:
                a=player.choose(g.observation(),random.Random(len(g.history)))
                z=player.choose(h.observation(),random.Random(len(h.history)))
                self.assertEqual((a.card,a.details),(z.card,z.details))
                g.play(a.card);h.play(z.card)
        finally: player.close()


if __name__ == '__main__': unittest.main()
