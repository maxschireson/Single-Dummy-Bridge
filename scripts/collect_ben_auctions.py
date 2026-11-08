#!/usr/bin/env python3
"""Collect hand-dependent auctions using a pinned external BEN neural bidder.

No search, DDS, rescue bidding or auxiliary hand-inference network is run.
Independent calls with the same sequence length share a neural inference batch.
BEN is GPL-3.0 (lorserker/ben); its source/models are external, not redistributed.
Records contain privileged full hands separately from public auction transcripts.
"""
import argparse
from collections import defaultdict
from dataclasses import replace
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.core import SEATS, auction_contract, hand_text
from bridge_harness.corpus import generate, load
from bridge_harness.training import digest, split_for


def file_sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ben-dir", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--exclude-groups", type=Path, required=True)
    p.add_argument("--count", type=int, default=1000)
    p.add_argument("--input-corpus", type=Path, help="Use these exact deals instead of generating new cards")
    p.add_argument("--seed", type=int, default=20261301)
    p.add_argument("--batch-size", type=int, default=128)
    p.add_argument("--verify-scalar", type=int, default=16)
    args = p.parse_args()
    ben, cfg, out = args.ben_dir.resolve(), args.config.resolve(), args.out.resolve()
    args.exclude_groups = args.exclude_groups.resolve()
    exclusions = json.loads(args.exclude_groups.read_text())
    excluded = set(exclusions["deal_ids"])
    if args.count < 1 or args.batch_size < 1: p.error("Positive count/batch required")
    if out.exists(): p.error("Refusing to overwrite an auction collection")
    boards = (load(args.input_corpus.resolve()) if args.input_corpus else
              [replace(b, id=f"{args.seed}-{b.id}") for b in generate(args.count, args.seed)])
    if len(boards) != args.count:
        raise ValueError("Input corpus count differs from --count")
    ids = [digest(b.hands) for b in boards]
    if len(set(ids)) != len(ids) or excluded.intersection(ids):
        raise ValueError("Duplicate/reserved deal: select a new seed")
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("TF_NUM_INTRAOP_THREADS", "1")
    os.environ.setdefault("TF_NUM_INTEROP_THREADS", "1")
    sys.path.insert(0, str(ben / "src")); os.chdir(ben)
    import numpy as np
    import tensorflow as tf
    import conf
    from nn.models_tf2 import Models
    from sample import Sample
    from botbidder import BotBid
    from bidding import bidding
    np.random.seed(42); tf.random.set_seed(42)
    config = conf.load(str(cfg))
    models = Models.from_conf(config, str(ben), False)
    sampler = Sample.from_conf(config, False)
    if models.model_version != 3 or models.use_bba or models.consult_bba:
        raise ValueError("This collector requires BEN v3 neural bidding without BBA")
    if models.search_threshold != -1 or models.check_final_contract or not sampler.no_samples_when_no_search:
        raise ValueError("Explicit neural-only configuration required")
    bidder_model = (ben / config['bidding']['bidder']).resolve()
    out.mkdir(parents=True); (out / "episodes").mkdir()
    manifest = dict(schema="ben-auction-only-v1", purpose="training/development auctions; no card play",
        seed=args.seed, requested_deals=args.count, deal_ids=ids, bidder="BEN-neural-only-batched",
        ben_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ben, text=True).strip(),
        model=str(config['bidding']['bidder']), model_sha256=file_sha(bidder_model),
        config_sha256=file_sha(cfg), collector_sha256=file_sha(__file__),
        exclusion_sha256=file_sha(args.exclude_groups), excluded_deals=len(excluded),
        tensorflow=tf.__version__, batch_size=args.batch_size, selection="best legal neural call",
        search=False, auxiliary_bidinfo=False, dds_calls=0,
        privacy="each neural input sees only bidder's own hand and public auction prefix",
        training_rule="full hands are targets only; future calls/contracts unavailable to prefix examples")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (out / "ben.conf").write_bytes(cfg.read_bytes())
    summary = dict(completed=0, passed_out=0, calls=0, failures=0,
                   splits={s: 0 for s in ('train', 'validation', 'test')},
                   scalar_checked=0, max_scalar_probability_difference=0.)
    start = time.perf_counter()
    with (out / "frozen.jsonl").open('x') as frozen:
        for offset in range(0, len(boards), args.batch_size):
            active = [dict(board=b, calls=[], transcript=[]) for b in boards[offset:offset+args.batch_size]]
            while active:
                groups = defaultdict(list)
                for item in active:
                    b, calls = item['board'], item['calls']
                    if len(calls) >= 320: raise ValueError("Auction exceeded legal length")
                    seat = (b.dealer + len(calls)) % 4
                    # This is the ONLY boundary into BEN's input encoder.
                    bot = BotBid([b.vulnerability in ('NS', 'Both'), b.vulnerability in ('EW', 'Both')],
                        hand_text(b.hands[seat]), models, sampler, seat, b.dealer, None, False, False)
                    auction = ['PAD_START'] * b.dealer + calls
                    x = bot.get_binary(auction, models)
                    groups[x.shape[1]].append((item, bot, auction, x, seat))
                next_active = []
                for group in groups.values():
                    x = np.concatenate([row[3] for row in group], axis=0)
                    probabilities, _ = models.bidder_model.pred_fun_seq(x)
                    if probabilities.shape != (len(group), x.shape[1], 40):
                        raise ValueError(f"Unexpected bidder shape {probabilities.shape}")
                    for j, (item, bot, auction, _, seat) in enumerate(group):
                        values = probabilities[j, -1]
                        if not np.isfinite(values).all(): raise ValueError("Nonfinite bidder output")
                        legal = [k for k in np.argsort(-values, kind='stable') if bidding.can_bid(bidding.ID2BID[k], auction)]
                        if not legal: raise ValueError("No legal call")
                        call = bidding.ID2BID[legal[0]]
                        if summary['scalar_checked'] < args.verify_scalar:
                            scalar, _ = bot.next_bid_np(auction)
                            diff = float(np.max(np.abs(values - scalar)))
                            scalar_legal = [k for k in np.argsort(-scalar, kind='stable') if bidding.can_bid(bidding.ID2BID[k], auction)]
                            if diff > 1e-4 or bidding.ID2BID[scalar_legal[0]] != call:
                                raise ValueError("Batched/scalar bidder mismatch")
                            summary['scalar_checked'] += 1
                            summary['max_scalar_probability_difference'] = max(summary['max_scalar_probability_difference'], diff)
                        item['calls'].append(call)
                        item['transcript'].append(dict(seat=SEATS[seat], bid=call,
                            neural_probability=float(values[legal[0]]), behavior_probability=1.))
                        summary['calls'] += 1
                        b = item['board']
                        try: contract = auction_contract(b.dealer, item['calls'])
                        except ValueError as e:
                            if str(e) != 'Incomplete auction': raise
                            next_active.append(item); continue
                        board = replace(b, contract=contract, auction=tuple(item['calls']),
                                        opening_lead=None, auction_source="BEN-neural-only-batched")
                        split = split_for(board)
                        episode = dict(schema="ben-auction-only-v1", metadata=dict(deal_id=digest(b.hands),
                            split_group=digest(b.hands), split=split, bidder=manifest['bidder']),
                            board=board.to_dict(), transcript=item['transcript'])
                        dest = out / 'episodes' / (digest(b.hands) + '.json.gz')
                        temporary = dest.with_suffix('.tmp')
                        with gzip.open(temporary, 'wt') as f: json.dump(episode, f)
                        temporary.replace(dest)
                        frozen.write(json.dumps(board.to_dict())+'\n'); frozen.flush()
                        summary['completed'] += 1; summary['passed_out'] += contract is None
                        summary['splits'][split] += 1
                active = next_active
            summary['seconds'] = time.perf_counter() - start
            summary['auctions_per_second'] = summary['completed'] / summary['seconds']
            (out / 'summary.json').write_text(json.dumps(summary, indent=2))
            print(json.dumps(summary), flush=True)
    assert summary['completed'] == args.count


if __name__ == '__main__': main()
