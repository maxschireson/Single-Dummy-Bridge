import ctypes as C
from dataclasses import replace
import gzip
import json
import random
import tempfile
import unittest
from pathlib import Path

from bridge_harness.core import Game, card, symbol
from bridge_harness.corpus import generate
from bridge_harness.dds import DDS, Deal, Future
from bridge_harness.players import PIMCPlayer
from bridge_harness.runner import run_pair, replay
from bridge_harness.sampling import Sampler
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import examples_from_record, input_tensors, split_for, split_identity, export_npz


class BatchTests(unittest.TestCase):
    def test_all_moves_match_independent_solves(self):
        rng = random.Random(997)
        dds = DDS()
        comparisons = 0
        try:
            for board in generate(5, seed=224):
                game = Game(board)
                while not game.done:
                    o = game.observation()
                    if len(o.history) // 4 in (0, 3, 6, 10, 12):
                        worlds = [Sampler(o).draw(rng) for _ in range(4)]
                        worlds.append(worlds[0])
                        expected = [dds.solve(h, o.contract.trump, o.leader, o.trick)[0] for h in worlds]
                        for retain in (True, False):
                            got = dds.solve_batch(worlds, o.contract.trump, o.leader, o.trick,
                                [s for s, h in enumerate(o.known_hands) if h is not None], retain)
                            self.assertEqual([x[0] for x in got], expected)
                            comparisons += len(worlds)
                    game.play(rng.choice(o.legal))
            self.assertEqual(comparisons, 1000)
        finally:
            dds.close()

    def test_reject_entire_batch_before_search(self):
        dds = DDS(); b = next(generate(1)); o = Game(b).observation()
        world = Sampler(o).draw(random.Random(3))
        try:
            bad = [list(h) for h in world]; bad[0].append(bad[0][0])
            with self.assertRaisesRegex(ValueError, "duplicate"):
                dds.solve_batch([world, bad], o.contract.trump, o.leader, ())
            bad = [list(h) for h in world]; bad[0][0], bad[1][0] = bad[1][0], bad[0][0]
            with self.assertRaisesRegex(ValueError, "fixed hand"):
                dds.solve_batch([world, bad], o.contract.trump, o.leader, (), [0])
            deals = (Deal * 2)(dds._deal(world, o.contract.trump, o.leader, ()),
                               dds._deal(world, o.contract.trump, o.leader, ()))
            deals[1].hands[0][0] |= 1  # invalid rank bit in the LAST layout
            output = (Future * 2)(); output[0].cards = -999
            error = C.create_string_buffer(512)
            result = dds.lib.bridge_dds_all_moves_batch(dds.ctx, deals, 2, 0, 1, output, error, len(error))
            self.assertEqual(result, -1)
            self.assertEqual(output[0].cards, -999)  # no first-world solve occurred
        finally:
            dds.close()

    def test_batch_and_serial_choose_same_moves(self):
        batch, serial = PIMCPlayer(8, "tricks", True, .125), PIMCPlayer(8, "tricks", False, .125)
        try:
            game = Game(next(generate(1, seed=41)))
            while not game.done:
                o = game.observation()
                a = batch.choose(o, random.Random(len(o.history)))
                b = serial.choose(o, random.Random(len(o.history)))
                self.assertEqual(a.card, b.card)
                self.assertEqual(a.details.get("estimates"), b.details.get("estimates"))
                probs = a.details["behavior_probabilities"]
                self.assertAlmostEqual(sum(probs.values()), 1)
                for c, p in probs.items():
                    if p and not a.details.get("forced"):
                        self.assertLessEqual(a.details["estimates"][c]["gap_to_best"], .125 + 1e-9)
                game.play(a.card)
        finally:
            batch.close(); serial.close()

    def test_no_extra_information_in_bot(self):
        a, b = list(generate(2, seed=71, family_size=2))
        lead = next(iter(set(a.hands[3]) & set(b.hands[3])))
        ga, gb = Game(a), Game(b); ga.play(lead); gb.play(lead)
        p = PIMCPlayer(4, "tricks", True, .125)
        try:
            da = p.choose(ga.observation(), random.Random(21))
            db = p.choose(gb.observation(), random.Random(21))
            self.assertEqual(da.card, db.card)
            self.assertEqual(da.details["estimates"], db.details["estimates"])
        finally:
            p.close()


class TrainingTests(unittest.TestCase):
    def test_complete_labels_masks_and_export(self):
        import numpy as np
        board = next(generate(1, seed=82))
        record = run_pair(board, dict(mode="selfplay", candidate="pimc", baseline="pimc",
            common="pimc", samples=4, objective="tricks", near_tie=.125))
        self.assertEqual(record["status"], "ok", record)
        replay(record)
        rows = json.loads(json.dumps(examples_from_record(record, "test-episode")))
        self.assertEqual(len(rows), 52)
        game = Game(board)
        for row in rows:
            o, target = row["observation"], row["belief_target"]
            inputs = input_tensors(o)
            played = {c for _, c in o["history"]}
            known = {c for h in o["known_hands"] if h is not None for c in h}
            for c, seat in enumerate(target["remaining_owner"]):
                self.assertEqual(target["unknown_mask"][c], c not in played | known)
                if c in played: self.assertEqual(seat, -1)
                else:
                    self.assertIn(c, game.hands[seat])
                    self.assertTrue(inputs["owner_support"][c, seat])
            self.assertEqual(set(o), {"controller", "actor", "known_hands", "legal", "history", "trick", "leader", "contract", "dealer", "vulnerability", "auction", "declarer_tricks"})
            policy = row["policy_target"]
            self.assertAlmostEqual(sum(policy["behavior_probabilities"].values()), 1)
            self.assertIn(policy["action"], o["legal"])
            self.assertLessEqual(policy["remaining_actor_tricks"], 13 - len(o["history"]) // 4)
            self.assertGreaterEqual(policy["remaining_actor_tricks"], 0)
            game.play(policy["action"])
        with tempfile.TemporaryDirectory() as td:
            atomic_json(Path(td) / "episodes/test.json.gz", dict(record=record, examples=rows), True)
            path = Path(td) / "train.npz"
            n = export_npz(td, path, split_for(board))
            self.assertEqual(n, 52)
            with np.load(path) as data:
                self.assertEqual(data["known"].shape, (52, 4, 52))
                self.assertEqual(data["owner_target"].shape, (52, 52))
                mask = data["owner_loss_mask"]
                ix, c = np.where(mask)
                self.assertTrue(data["owner_support"][ix, c, data["owner_target"][ix, c]].all())

    def test_related_and_repeat_splits_stay_together(self):
        boards = list(generate(8, seed=739, family_size=8))
        self.assertEqual(len({split_identity(b) for b in boards}), 1)
        self.assertEqual(len({split_for(b) for b in boards}), 1)
        self.assertEqual(split_identity(boards[0]), split_identity(replace(boards[0], id="another-id", family="renamed")))

    def test_failed_games_are_not_training_examples(self):
        self.assertEqual(examples_from_record({"status": "timeout"}, "bad"), [])


if __name__ == "__main__":
    unittest.main()
