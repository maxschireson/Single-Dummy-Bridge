#!/usr/bin/env python3
"""scripts/plan_bench.py with the 8X rollouts as simulated seats, so that scripts/plan_headroom.py can score them
against the plan session's ceilings.

  SURE_BIN=... python scripts/x8_bench.py --episodes DIR --nets v41=PATH --sims "v41:xc;v41:xt" --from-trick 7 --to-trick 12 \\
      --seed 1 --workers 2 --out rows.json

Every argument is plan_bench's. Two more seat modes:

  xt   bridge_harness.x8_rollout.evaluate with the net's top card at every seat: the same rollouts as plan_bench's
       `top`, through the 8X code
  xc   the same with the claim finder at the start of tricks with 6 or fewer cards (x8_claims.Finder.boundaries): the
       declaring side's result floored at the contract where its own view guarantees it, and a rollout ended where it
       guarantees every trick left, as the 8X bot's rollouts are for a side it treats as keeping a guaranteed contract

Rows and their fields are plan_bench's.
"""
import os
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import plan_bench  # noqa: E402
from bridge_harness import x8_claims  # noqa: E402
from bridge_harness.plan_rollout import NetPlayer  # noqa: E402
from bridge_harness.x8_rollout import Seats, evaluate  # noqa: E402

LEAF = int(os.environ.get('X8_BENCH_LEAF', '6'))


class X8Seat(NetPlayer):
    """A marker: plan_bench builds it in place of its seat player, and card_values below sends it to x8_rollout."""

    def __init__(self, net, claims):
        super().__init__(net, 'top')
        self.claims = claims


_seat_player = plan_bench.seat_player
_card_values = plan_bench.card_values


def seat_player(net, dds, mode, seed):
    if mode in ('xt', 'xc'):
        return X8Seat(net, mode == 'xc')
    return _seat_player(net, dds, mode, seed)


def card_values(o, worlds, cards, player, public=None, repeats=1, tricks=0, dds=None):
    if not isinstance(player, X8Seat):
        return _card_values(o, worlds, cards, player, public, repeats, tricks, dds)
    finder = x8_claims.shared() if player.claims else None
    got = evaluate(o, worlds, cards, Seats([player.net]).start(o), horizon=tricks, dds=dds, finder=finder,
                   target=o.contract.level + 6, leaf_cards=LEAF)
    target = o.contract.level + 6
    final = np.where(got.floor, np.maximum(got.tricks, target), got.tricks).astype(float)
    declaring = o.controller % 2 == o.contract.declarer % 2
    return final if declaring else -final


plan_bench.seat_player = seat_player
plan_bench.card_values = card_values

if __name__ == '__main__':
    plan_bench.main()
