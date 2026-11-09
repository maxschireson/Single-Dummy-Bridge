import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from bridge_harness.bidding_belief_data import (belief_split, committed_batches,
    examples, overlaps, export)
from bridge_harness.bidding_env import make_board, deal_key
from bridge_harness.core import Board
from bridge_harness.training import digest
from scripts.train_bidding_belief import acceptable, batch


class BiddingBeliefTest(unittest.TestCase):
    def setUp(self):
        self.board = make_board(1945, 8, 'train')

    def test_rooms_rotations_and_prefixes_share_split(self):
        h = self.board.hands
        keys = [deal_key(h[i:]+h[:i],True) for i in range(4)]
        self.assertEqual(len(set(keys)),1)
        self.assertEqual(len({belief_split(k) for k in keys}),1)
        rows = list(examples(self.board,('PASS',)*4,keys[0]))
        self.assertEqual(len(rows),8)
        for r in rows:
            self.assertEqual(r['owner_loss_mask'].sum(),39)
            np.testing.assert_array_equal(r['state'][:52] != 0,r['owner_target']==0)
            self.assertEqual(r['split_group'],keys[0])

    def test_hidden_cards_are_labels_not_features(self):
        b = self.board
        hands = [list(h) for h in b.hands]
        hands[1][0],hands[2][0] = hands[2][0],hands[1][0]
        other = Board('other',tuple(tuple(sorted(h)) for h in hands),None,b.dealer,b.vulnerability)
        first = list(examples(b,('PASS',)*4,'same'))[:2]
        second = list(examples(other,('PASS',)*4,'same'))[:2]
        for a,c in zip(first,second):
            for k in ('state','calls','seats'):
                np.testing.assert_array_equal(a[k],c[k])
            self.assertFalse(np.array_equal(a['owner_target'],c['owner_target']))

    def test_pre_call_views_exclude_future(self):
        b = self.board
        calls = ('1N','PASS','3N','PASS','PASS','PASS')
        for observer in range(4):
            r = list(examples(b,calls,'same'))[2*observer]
            length = np.count_nonzero(r['calls'])
            self.assertLess(length,len(calls))
            self.assertEqual((b.dealer+length)%4,observer)
            self.assertTrue(np.all(r['seats'][length:]==4))

    def test_reserved_deal_detected_in_any_rotation(self):
        h = self.board.hands
        for i in range(4):
            self.assertTrue(overlaps(h,{digest(h[i:]+h[:i])}))
        self.assertFalse(overlaps(h,{'unrelated'}))

    def test_uncommitted_and_evaluation_rows_not_imported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('a001-0000000','a001-0000002'):
                d = root/'batches'/name
                d.mkdir(parents=True)
                (d/'auctions.json').write_text(json.dumps([{},{}]))
                (d/'metrics.json').write_text('{"pairs":2}')
            state = dict(attempt=1,trained_pairs=2,total_train_pairs=2)
            with patch('bridge_harness.bidding_env.TableSolver.solve',side_effect=AssertionError('DDS forbidden')):
                found = list(committed_batches(root,{},state))
            self.assertEqual(len(found),1)
            self.assertEqual(found[0][3],0)
            state['trained_pairs']=5
            state['total_train_pairs']=5
            with self.assertRaisesRegex(ValueError,'Expected 5 committed'):
                list(committed_batches(root,{},state))

    def test_original_bidder_validation_protects_parent(self):
        def metrics(ben,new):
            return {s:{k:dict(nll=v) for k in ('all','complete_auction')}
                    for s,v in (('ben',ben),('bidding',new))}
        parent = metrics(1.,1.)
        self.assertTrue(acceptable(metrics(.99,.98),parent,1.))
        self.assertFalse(acceptable(metrics(1.01,.9),parent,1.))
        self.assertFalse(acceptable(parent,parent,1.))

    def test_support_built_only_from_own_input(self):
        rows = list(examples(self.board,('PASS',)*4,'same'))
        data = {k:np.stack([r[k] for r in rows]) for k in rows[0]}
        x,y,m,support = batch(data,slice(None))
        self.assertTrue(np.take_along_axis(support,y[...,None],-1).all())
        self.assertTrue(np.all(m.sum(-1)==39))
        self.assertEqual(set(x),{'state','calls','seats'})


if __name__ == '__main__':
    unittest.main()
