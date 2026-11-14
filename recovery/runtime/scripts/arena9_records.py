#!/usr/bin/env python3
"""Re-create the full board records of an arena epoch from its control directory, for diagnosis.

The runner keeps a row per board, not its record. Play is seeded, so playing a board again from its epoch manifest
and snapshot gives the same record; each re-created record's trace is checked against the row the run wrote.

    python scripts/arena9_records.py --control RUN/control --players configs/players --capsule CAPSULE/recovery \\
        --epoch 5 --pair 9a-32~guest-b --floor --out records/e5-9a-32~guest-b.jsonl.gz --workers 2

Writes one JSON record a line (gzip), appended, so an interrupted run resumes; prints how many traces matched.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import arena9 as A  # noqa: E402
from bridge_harness import arena9 as a9  # noqa: E402
from bridge_harness import arena9_pipeline as pl  # noqa: E402


def _record(index, seed):
    from bridge_harness.gen5_arena import run_board
    G = A._load_gen9_match()
    m, source = A.WORKER['m'], A.WORKER['source']
    board = G.deal(seed, index)
    r = run_board(source, m, board.to_dict(), index, G.g8.STATE['bidders'], player_factory=G.player)
    return index, r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--control', type=Path, required=True)
    ap.add_argument('--players', type=Path, required=True)
    ap.add_argument('--capsule', type=Path, required=True)
    ap.add_argument('--epoch', type=int, required=True)
    ap.add_argument('--pair', required=True)
    ap.add_argument('--floor', action='store_true', help='only the floor boards of the pair')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    rows = {r['index']: r for r in a9.read_results(a.control) if r['epoch'] == a.epoch and r['pair'] == a.pair and (not a.floor or r.get('floor') is not None)}
    done = set()
    if a.out.exists():
        with gzip.open(a.out, 'rt') as f:
            done = {json.loads(l)['_index'] for l in f if l.strip()}
    todo = [i for i in sorted(rows) if i not in done][:a.limit]
    m = json.loads(a9.epoch_path(a.control, a.epoch).read_text())
    mb = A.MatchBackend(a9.load_packages(a.players), a.capsule, control=a.control)
    seed = m['deals']['seed']
    man, models = mb.manifest(m, a.pair, seed)
    ctx = dict(epoch_id=m['id'], pair=a.pair, models=models or {}, declared={}, experience=False, occasions=None, reading=None)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    same = differ = 0
    with ProcessPoolExecutor(a.workers, initializer=A._worker_start, initargs=(str(mb.capsule), man, ctx)) as ex, gzip.open(a.out, 'at') as out:
        for index, r in ex.map(_record, todo, [seed] * len(todo)):
            ok = pl.trace(r) == rows[index]['trace']
            same += ok
            differ += not ok
            out.write(json.dumps(dict(r, _index=index, _epoch=a.epoch, _pair=a.pair, _trace_matches=ok)) + '\n')
            out.flush()
    print(json.dumps(dict(pair=a.pair, epoch=a.epoch, written=same + differ, trace_matches=same, trace_differs=differ, already=len(done))))


if __name__ == '__main__':
    main()
