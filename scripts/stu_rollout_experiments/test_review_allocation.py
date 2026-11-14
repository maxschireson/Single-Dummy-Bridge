"""Focused regression checks for PR #38's allocation bookkeeping.

STU_RUNTIME and STU_EXPERIMENT_SOURCE identify immutable external checkouts.
These synthetic fixtures isolate scheduling logic, not model or playing strength.
Exit nonzero until the three expected allocation properties hold.
"""
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(os.environ['STU_RUNTIME']).resolve()),
               str(Path(__file__).resolve().parent)]
import numpy as np
import engine
from bridge_harness.players import Decision


class RowsFixture:
    def __init__(self, n=1):
        self.o = SimpleNamespace(history=())
        self.played = 1
        self.holder = np.zeros((n, 52), dtype=np.int8)
        for i in range(n):
            self.holder[i, i] = 1  # distinct simulator path keys
        self.by = np.full((n, 52), -1, dtype=np.int8)
        self.order = np.zeros((n, 52), dtype=np.int8)
        self.order[:, 0] = 1
        self.views = [SimpleNamespace(legal=(2, 3), controller=0, label=i) for i in range(n)]

    def controller(self):
        return np.zeros(len(self.views), dtype=int)


def setup_owner(mode='uniform', calls=0, maximum=4, child_card=3):
    owner = SimpleNamespace(
        experiment=dict(recursive=mode, window_plies=8, max_calls=maximum, logp_margin=1.),
        recursive_stats=dict(opportunities=0, calls=calls, cache_hits=0, changed=0, net_rows=0),
        recursive_cache={},
        child_player=lambda: SimpleNamespace(choose=lambda o, rng: Decision(child_card, {})))
    seats = engine.ReplanningSeats([], owner=owner)
    seats.side = 0
    return owner, seats


def base_cards(rows, *, chosen=2, gap=5.):
    n = len(rows.views)
    lp = np.full((n, 52), -100.)
    lp[:, 2], lp[:, 3] = 0., -gap
    return np.full(n, chosen, dtype=int), np.arange(n), lp


class AllocationProperties(unittest.TestCase):
    def test_confident_first_node_does_not_block_later_uncertain_node(self):
        rows = RowsFixture()
        owner, seats = setup_owner('selective')
        with patch.object(engine, 'row_view', side_effect=lambda r, i: r.views[i]):
            with patch.object(engine.Seats, 'cards', side_effect=lambda r, other=None: base_cards(r, gap=5.)):
                seats.cards(rows)
            self.assertEqual(owner.recursive_stats['calls'], 0)
            rows.played = 3
            rows.views[0] = SimpleNamespace(legal=(2, 3), controller=0, label='later')
            with patch.object(engine.Seats, 'cards', side_effect=lambda r, other=None: base_cards(r, gap=0.)):
                seats.cards(rows)
        self.assertEqual(owner.recursive_stats['calls'], 1,
                         'The later uncertain own decision was suppressed by the earlier confident one')

    def test_budget_cap_does_not_suppress_later_cache_hits(self):
        rows = RowsFixture(2)
        owner, seats = setup_owner(calls=1, maximum=1)
        keys = [(engine.view_seed(o), i) for i, o in enumerate(rows.views)]
        _, cached_i = max(keys)
        owner.recursive_cache[engine.view_seed(rows.views[cached_i])] = 3
        with patch.object(engine, 'row_view', side_effect=lambda r, i: r.views[i]), \
                patch.object(engine.Seats, 'cards', side_effect=lambda r, other=None: base_cards(r)):
            cards, _, _ = seats.cards(rows)
        self.assertEqual(int(cards[cached_i]), 3, 'An earlier uncached opportunity stopped cache processing')
        self.assertEqual(owner.recursive_stats['cache_hits'], 1)
        self.assertEqual(owner.recursive_stats['calls'], 1)

    def test_changed_counts_replacement_of_actual_drawn_card(self):
        rows = RowsFixture()
        owner, seats = setup_owner(child_card=3)
        with patch.object(engine, 'row_view', side_effect=lambda r, i: r.views[i]), \
                patch.object(engine.Seats, 'cards', side_effect=lambda r, other=None: base_cards(r, chosen=3)):
            cards, _, _ = seats.cards(rows)
        self.assertEqual(int(cards[0]), 3)
        self.assertEqual(owner.recursive_stats['calls'], 1)
        self.assertEqual(owner.recursive_stats['changed'], 0,
                         'Child retained the drawn card, but changed was measured against policy argmax')


if __name__ == '__main__':
    unittest.main(verbosity=2)
