#!/usr/bin/env python3
"""Does a collection worker's memory grow board after board? One process plays pure Stu's self-play boards the way a
worker of the collection does (x8_match's start, then gen8_match.play for each board, one table a board) and prints its
resident memory after each board, before and after a full garbage collection:

  python training/rollout-loop-20261113/bench/memory.py --boards 25 [--pair stu0-pa~stu0-pb] [--first 900000]

Set BRIDGE_NET_BF16 as the collection does (run.sh sets it to 1 for runs named sp*) to compare the two paths.
"""
import argparse, gc, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'scripts'))
import x8_match  # noqa: E402
import gen8_match  # noqa: E402


def rss_mb():
    for line in open('/proc/self/status'):
        if line.startswith('VmRSS:'):
            return int(line.split()[1]) / 1024
    return float('nan')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--boards', type=int, default=25)
    p.add_argument('--pair', default='stu0-pa~stu0-pb')
    p.add_argument('--first', type=int, default=900000)
    p.add_argument('--source', type=Path, default=Path.home() / 'work/loop/capsule/recovery')
    a = p.parse_args()
    m = x8_match.build_manifest(a.source, ROOT / 'configs/loop-bots.json', a.pair, 9001)
    m['one_room'] = True
    x8_match.start(str(a.source), m)
    print(f'bf16 {os.environ.get("BRIDGE_NET_BF16", "0")}, pair {a.pair}; after start {rss_mb():.0f} MB', flush=True)
    for k in range(a.boards):
        t = time.time()
        gen8_match.play(a.first + k, 9001, None)
        before = rss_mb()
        found = gc.collect()
        print(f'board {k + 1}: {time.time() - t:5.1f} s, {before:6.0f} MB, after gc {rss_mb():6.0f} MB ({found} objects)', flush=True)


if __name__ == '__main__':
    main()
