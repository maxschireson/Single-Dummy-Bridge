"""Check the Gen 6 candidate bidder with the harness's own bidding code.

1. Rebuilds bidder.keras from its chunks, checking every SHA-256.
2. Loads it with bridge_harness.bidding_ppo.Policy.load and bids the 2,270 solved test deals
   greedily in both rooms against the Gen 5 bidder (bridge_harness.bidding_env.paired_auctions),
   scoring each contract from the deal's stored double-dummy table.

Expected output: +0.331 +- 0.068 IMPs/board, 223 won / 141 lost / 1906 tied.

usage: python verify_candidate.py --gen5 PATH/TO/gen5/bidder.keras [--harness DIR] [--deals FILE]

Needs TensorFlow. --harness is a checkout that contains bridge_harness/bidding_env.py (any Gen 5 or
Gen 6 branch); it defaults to this repository. --deals defaults to
training/graded-alternatives-20261110/data/new_test_seed1911102026.jsonl.gz in this repository.
"""
import argparse
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

GEN5_SHA256 = '9ee52f3baa79c837001e0cb515c61a9a179cb1bf66cd5503e46331245c014dcc'


def restore(root):
    model = json.loads((root / 'manifest.json').read_text())['model']
    blocks = []
    for part in model['chunks']:
        data = (root / part['file']).read_bytes()
        if len(data) != part['bytes'] or hashlib.sha256(data).hexdigest() != part['sha256']:
            raise ValueError('Changed or missing chunk: ' + part['file'])
        blocks.append(data)
    data = b''.join(blocks)
    if len(data) != model['bytes'] or hashlib.sha256(data).hexdigest() != model['sha256']:
        raise ValueError('Model mismatch')
    target = root / model['file']
    if not target.exists() or target.read_bytes() != data:
        target.write_bytes(data)
    return target, model['sha256']


def main():
    here = Path(__file__).resolve().parent
    repo = here.parents[2]
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--gen5', type=Path, required=True)
    p.add_argument('--harness', type=Path, default=repo)
    p.add_argument('--deals', type=Path, default=repo / 'training/graded-alternatives-20261110/data/new_test_seed1911102026.jsonl.gz')
    p.add_argument('--threads', type=int, default=2)
    a = p.parse_args()
    if not (a.harness / 'bridge_harness' / 'bidding_env.py').exists():
        sys.exit(f'{a.harness} has no bridge_harness/bidding_env.py; pass --harness with a Gen 5 or Gen 6 checkout')
    target, digest = restore(here)
    print(f'restored {target.name}: sha256 {digest}', flush=True)
    gen5_digest = hashlib.sha256(a.gen5.read_bytes()).hexdigest()
    if gen5_digest != GEN5_SHA256:
        print(f'note: --gen5 is not the Gen 5 bidder (sha256 {gen5_digest[:8]}...); the expected figures do not apply', flush=True)

    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
    sys.path.insert(0, str(a.harness))
    import numpy as np
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(a.threads)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    from bridge_harness.bidding_ppo import Policy
    from bridge_harness.bidding_env import paired_auctions, deal_key
    from bridge_harness.core import Board, parse_hand, SEATS

    with gzip.open(a.deals, 'rt') as f:
        rows = [json.loads(line) for line in f]
    boards, tables = [], []
    for r in rows:
        hands = tuple(parse_hand(h) for h in r['hands'])
        boards.append(Board(deal_key(hands), hands, None, SEATS.index(r['dealer']), r['vulnerability']))
        tables.append(r['dds'])
    candidate, gen5 = Policy.load(target), Policy.load(a.gen5)
    values = []
    for start in range(0, len(boards), 256):
        b, t = boards[start:start + 256], tables[start:start + 256]
        batch, _ = paired_auctions(b, t, candidate, [gen5] * len(b), np.random.default_rng(0), explore=False)
        values.extend(r['imps'] for r in batch)
        print(json.dumps(dict(completed=len(values), target=len(boards))), flush=True)
    x = np.array(values, float)
    result = dict(deals=len(x), mean_imps=round(float(x.mean()), 4), se=round(float(x.std(ddof=1) / np.sqrt(len(x))), 4),
                  won=int((x > 0).sum()), lost=int((x < 0).sum()), tied=int((x == 0).sum()),
                  candidate_sha256=digest, gen5_sha256=gen5_digest, tensorflow=tf.__version__)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
