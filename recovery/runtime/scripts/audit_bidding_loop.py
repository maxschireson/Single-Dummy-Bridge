#!/usr/bin/env python3
"""Compare the interoperable encoder/legality to external BEN, and benchmark DDS."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
os.environ.setdefault('TF_NUM_INTRAOP_THREADS', '2')
os.environ.setdefault('TF_NUM_INTEROP_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ben-dir', required=True, type=Path)
    p.add_argument('--model', required=True, type=Path)
    p.add_argument('--dds-library', required=True, type=Path)
    p.add_argument('--boards', type=int, default=64)
    p.add_argument('--out', type=Path)
    args = p.parse_args()
    import numpy as np
    from bridge_harness.bidding_env import (BidObservation, CALLS, encode, legal_mask,
        make_board, masked_probabilities, pack_inputs, paired_auctions, TableSolver)
    from bridge_harness.bidding_ppo import Policy
    from bridge_harness.core import auction_contract, hand_text
    sys.path.insert(0, str(args.ben_dir.resolve()/'src'))
    import binary as ben_binary
    from bidding import bidding as ben_bidding
    from nn.bidder_tf2 import Bidder
    official = Bidder('audit', str(args.model.resolve()), False)
    model_info = SimpleNamespace(n_cards_bidding=24, model_version=3, adjust_hcp=False, ns=1, ew=1)
    model = Policy.load(args.model)
    boards = [make_board(2026110819, i, 'dev') for i in range(args.boards)]
    active = [(b, []) for b in boards]
    checked = max_error = max_probability_error = 0
    started = time.monotonic()
    while active:
        inputs = []
        for board, calls in active:
            seat = (board.dealer+len(calls)) % 4
            obs = BidObservation(board.hands[seat], seat, board.dealer, board.vulnerability, tuple(calls))
            ours = encode(obs)
            auction = ['PAD_START']*board.dealer+calls
            hand = ben_binary.parse_hand_f(24)(hand_text(obs.hand))
            original = ben_binary.get_auction_binary(len(ours), auction, seat, hand,
                [board.vulnerability in ('NS','Both'), board.vulnerability in ('EW','Both')], model_info)[0]
            error = float(np.max(np.abs(ours-original)))
            max_error = max(error, max_error)
            np.testing.assert_array_equal(ours, original)
            expected = np.array([ben_bidding.can_bid(c, auction) for c in CALLS])
            np.testing.assert_array_equal(legal_mask(board.dealer, calls), expected)
            checked += 1; inputs.append(ours)
        x, lengths = pack_inputs(inputs)
        probs, _ = model.predict(x, lengths)
        official_probs, _ = official.pred_fun_seq(x.astype(np.float16))
        expected_probs = official_probs[np.arange(len(x)), lengths-1]
        max_probability_error = max(max_probability_error, float(np.max(np.abs(probs-expected_probs))))
        np.testing.assert_allclose(probs, expected_probs, atol=1e-5, rtol=1e-4)
        next_active = []
        for (board, calls), prob in zip(active, probs):
            calls.append(CALLS[int(np.argmax(masked_probabilities(prob, legal_mask(board.dealer, calls))))])
            try:
                auction_contract(board.dealer, calls)
            except ValueError as exc:
                if str(exc) != 'Incomplete auction':
                    raise
                next_active.append((board, calls))
        active = next_active
    auction_seconds = time.monotonic()-started
    solver = TableSolver(args.dds_library)
    begin = time.monotonic()
    tables = [solver.solve(b.hands) for b in boards[:8]]
    dds_seconds = time.monotonic()-begin
    rows, _ = paired_auctions(boards[:8], tables, model, [model]*8, np.random.default_rng(1))
    assert all(r['imps'] == 0 for r in rows)
    result = dict(boards=args.boards, decisions_checked=checked, max_feature_difference=max_error,
                  max_probability_difference=max_probability_error,
                  legality_matches=True, identical_bidder_pairs=8, identical_pair_imps=0,
                  auction_audit_seconds=auction_seconds, dd_tables=8,
                  dd_table_seconds=dds_seconds, mean_dd_table_seconds=dds_seconds/8,
                  model_parameters=model.model.count_params())
    print(json.dumps(result, indent=2))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
