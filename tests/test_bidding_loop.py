"""Bidding score orientation, legality, information boundaries, and PPO checks."""
from dataclasses import replace
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np

from bridge_harness.bidding_env import (BidObservation, CALL_ID, TableSolver,
    deal_key, deal_split, encode, legal_mask, make_board, masked_probabilities,
    pack_inputs, paired_auctions, terminal_score)
from bridge_harness.core import Board
from bridge_harness.bidding_loop import Config, promotion


class PassPolicy:
    def predict(self, x, lengths):
        p = np.zeros((len(x), 40)); p[:, 2] = 1
        return p, np.zeros(len(x))


class AceSpadePolicy:
    def predict(self, x, lengths):
        p = np.zeros((len(x), 40))
        for i in range(len(x)):
            p[i, CALL_ID['4S'] if x[i, 0, 9] else CALL_ID['PASS']] = 1
        return p, np.zeros(len(x))


class BiddingTests(unittest.TestCase):
    def test_score_and_reward_orientation(self):
        b = make_board(123, 0, 'train')
        b = replace(b, dealer=0, vulnerability='NS')
        table = [[10]*4 for _ in range(5)]
        self.assertEqual(terminal_score(b, ['4S', 'PASS', 'PASS', 'PASS'], table), 620)
        self.assertEqual(terminal_score(b, ['PASS', '4S', 'PASS', 'PASS', 'PASS'], table), -420)
        self.assertEqual(terminal_score(b, ['PASS']*4, table), 0)
        table[0][0] = 8
        self.assertEqual(terminal_score(b, ['4S', 'X', 'PASS', 'PASS', 'PASS'], table), -500)
        self.assertEqual(terminal_score(b, ['4S', 'X', 'XX', 'PASS', 'PASS', 'PASS'], table), -1000)

    def test_declarer_first_strain_bidder(self):
        b = replace(make_board(123, 1, 'train'), dealer=0, vulnerability='None')
        table = [[9, 0, 11, 0] for _ in range(5)]
        calls = ['1S', 'PASS', '4S', 'PASS', 'PASS', 'PASS']
        self.assertEqual(terminal_score(b, calls, table), -50)

    def test_legality_double_redouble_and_padding(self):
        m = legal_mask(0, ['1S', 'X'])
        self.assertTrue(m[CALL_ID['XX']]); self.assertFalse(m[CALL_ID['X']])
        self.assertFalse(m[CALL_ID['1H']]); self.assertTrue(m[CALL_ID['1N']])
        self.assertFalse(m[:2].any())
        with self.assertRaises(ValueError):
            legal_mask(0, ['PASS']*4)

    def test_private_information_and_prefix(self):
        b = make_board(124, 1, 'train')
        obs = BidObservation(b.hands[0], 0, 0, 'None', ('1C', 'PASS', '1H', 'PASS'))
        x = encode(obs)
        self.assertEqual(x.shape, (2, 193))
        self.assertEqual(x[1, 33+CALL_ID['1C']], 1)
        self.assertEqual(x[1, 113+CALL_ID['1H']], 1)
        self.assertEqual(x[0, 33], 1)
        self.assertEqual(x[0, 9:33].sum(), 13)
        # No actual board, partner hand, result or future transcript in capability.
        self.assertEqual(set(obs.__dataclass_fields__), {'hand', 'seat', 'dealer', 'vulnerability', 'calls'})
        other = replace(obs, calls=('1D', 'PASS', '1H', 'PASS'))
        self.assertFalse(np.array_equal(x, encode(other)))

    def test_rotations_and_vulnerability_do_not_cross_splits(self):
        for split in ('train', 'dev', 'test'):
            b = make_board(124, 2, split)
            self.assertEqual(deal_split(b.hands), split)
            for i in range(4):
                hands = b.hands[i:]+b.hands[:i]
                self.assertEqual(deal_split(hands), split)
                self.assertEqual(deal_key(hands, True), deal_key(b.hands, True))

    def test_identical_greedy_bidders_tie(self):
        boards = [make_board(125, i, 'train') for i in range(8)]
        p = PassPolicy()
        rows, d = paired_auctions(boards, [[[7]*4]*5]*8, p, [p]*8, np.random.default_rng(2))
        self.assertEqual([r['imps'] for r in rows], [0]*8)
        self.assertFalse(d)

    def test_masked_exploration_support(self):
        mask = legal_mask(0, ['7N', 'X'])
        p = masked_probabilities(np.ones(40)/40, mask, .01)
        self.assertAlmostEqual(p.sum(), 1.)
        self.assertFalse(p[~mask].any())
        self.assertEqual(set(np.flatnonzero(p)), {CALL_ID['PASS'], CALL_ID['XX']})

    def test_both_candidate_rooms_receive_winning_team_reward(self):
        hands = tuple(tuple(range(s*13, (s+1)*13)) for s in range(4))
        b = Board('orientation', hands, None, 0, 'NS')
        rows, decisions = paired_auctions([b], [[[10]*4]*5], AceSpadePolicy(),
            [PassPolicy()], np.random.default_rng(19), explore=True, epsilon=0.)
        self.assertEqual(rows[0]['tables'][0]['ns_score'], 620)
        self.assertEqual(rows[0]['tables'][1]['ns_score'], 0)
        self.assertEqual(rows[0]['imps'], 12)
        self.assertTrue(decisions)
        self.assertTrue(all(d['reward'] == 12 for d in decisions))

    def test_gate_never_promotes_ties_or_repeated_deals(self):
        rows = [dict(deal_id=str(i), vs_parent=0, vs_original=0, vs_league=0) for i in range(10)]
        self.assertFalse(promotion(rows, 1, 3)['promoted'])
        with self.assertRaises(ValueError):
            promotion(rows+[rows[0]], 1, 3)
        rows = [dict(deal_id=str(i), **{k: 2+i%2 for k in ('vs_parent','vs_original','vs_league')})
                for i in range(100)]
        self.assertTrue(promotion(rows, 1, 3)['promoted'])
        self.assertLess(promotion(rows, 2, 3)['adjusted_alpha'], promotion(rows, 1, 3)['adjusted_alpha'])

    def test_config_rejects_invalid_stages(self):
        with self.assertRaises(ValueError):
            Config(train_stages=(100, 50)).validate()


@unittest.skipUnless(os.environ.get('BRIDGE_DDS_LIBRARY'), 'DDS integration requires BRIDGE_DDS_LIBRARY')
class DDSTests(unittest.TestCase):
    def test_known_complete_suits_and_random_opening_solve(self):
        solver = TableSolver(os.environ['BRIDGE_DDS_LIBRARY'])
        hands = tuple(tuple(range(s*13, (s+1)*13)) for s in range(4))
        table = solver.solve(hands)
        for strain in range(4):
            self.assertEqual(table[strain], [13 if seat%2==strain%2 else 0 for seat in range(4)])
        self.assertEqual(table[4], [0]*4)
        b = make_board(125, 2, 'train')
        table = solver.solve(b.hands)
        for strain, declarer in [(0,0), (1,1), (2,2), (3,3), (4,0)]:
            scores, _ = solver.dds.solve(b.hands, strain, (declarer+1)%4, ())
            self.assertEqual(table[strain][declarer], 13-max(scores.values()))


@unittest.skipUnless(importlib.util.find_spec('tensorflow'), 'TensorFlow optional')
class PPOTests(unittest.TestCase):
    def test_advantage_updates_policy_and_resume_restores_adam(self):
        import tensorflow as tf
        from bridge_harness.bidding_ppo import Policy, PPO
        tf.keras.utils.set_random_seed(77)
        inp = tf.keras.Input((None, 193))
        hidden = tf.keras.layers.Dense(8, activation='tanh')(inp)
        probs = tf.keras.layers.Dense(40, activation='softmax')(hidden)
        values = tf.keras.layers.Dense(1, kernel_initializer='zeros', bias_initializer='zeros')(hidden)
        policy = Policy(tf.keras.Model(inp, [probs, values]))
        anchor = Policy(tf.keras.models.clone_model(policy.model))
        anchor.model.set_weights(policy.model.get_weights())
        trainer = PPO(policy, anchor, learning_rate=.001, epsilon=.005, anchor_weight=0.)
        b = make_board(127, 0, 'train')
        x = encode(BidObservation(b.hands[0], 0, 0, 'None', ()))
        xx, ll = pack_inputs([x]); mask = legal_mask(0, [])
        before, _ = policy.predict(xx, ll)
        p = masked_probabilities(before[0], mask, .005)
        d = dict(x=x, mask=mask, action=2, old_logp=np.log(p[2]), old_value=0., reward=10.)
        trainer.train([d]*16, np.random.default_rng(1), epochs=1, batch_size=16)
        after, _ = policy.predict(xx, ll)
        self.assertGreater(after[0, 2], before[0, 2])
        with tempfile.TemporaryDirectory() as tmp:
            cp = trainer.save(Path(tmp)/'ckpt')
            saved = [v.numpy().copy() for v in trainer.optimizer.variables]
            model_path = Path(tmp)/'model.keras'; policy.save(model_path)
            other = Policy.load(model_path, critic=True)
            restored = PPO(other, anchor, learning_rate=.001, epsilon=.005, anchor_weight=0.)
            restored.restore(cp)
            np.testing.assert_allclose(other.predict(xx,ll)[0], after, atol=1e-7)
            for expected, actual in zip(saved, restored.optimizer.variables):
                np.testing.assert_array_equal(actual.numpy(), expected)


if __name__ == '__main__':
    unittest.main()
