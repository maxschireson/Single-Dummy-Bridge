#!/usr/bin/env python3
"""Paired serial/retained PIMC timing on identical worlds and observations."""
import argparse
import json
from pathlib import Path
import random
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.core import Game
from bridge_harness.corpus import generate
from bridge_harness.players import PIMCPlayer


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--boards", type=int, default=20)
    p.add_argument("--samples", type=int, default=32)
    p.add_argument("--repeats", type=int, default=2)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    positions = []
    rng = random.Random(1881)
    for b in generate(args.boards, seed=18391):
        g = Game(b)
        while not g.done:
            o = g.observation()
            if len(g.history) // 4 in (0, 3, 6, 9) and len(o.legal) > 1:
                positions.append(o)
            g.play(rng.choice(o.legal))
    players = {mode: PIMCPlayer(args.samples, "tricks", mode == "batch", .125) for mode in ("serial", "batch")}
    rows = []
    try:
        for repeat in range(args.repeats):
            for i, o in enumerate(positions):
                decisions = {}
                for mode in (("serial", "batch") if (i + repeat) % 2 == 0 else ("batch", "serial")):
                    start = time.perf_counter()
                    decisions[mode] = d = players[mode].choose(o, random.Random(79231 + i))
                    rows.append(dict(repeat=repeat, position=i, ply=len(o.history),
                        remaining_tricks=13 - len(o.history) // 4, mode=mode,
                        seconds=time.perf_counter() - start, nodes=d.details["dds_nodes"]))
                assert decisions["serial"].card == decisions["batch"].card
                assert decisions["serial"].details["estimates"] == decisions["batch"].details["estimates"]
    finally:
        for player in players.values(): player.close()
    totals = {mode: sum(r["seconds"] for r in rows if r["mode"] == mode) for mode in players}
    by_size = {}
    for size in sorted({r["remaining_tricks"] for r in rows}, reverse=True):
        timing = {mode: sum(r["seconds"] for r in rows if r["mode"] == mode and r["remaining_tricks"] == size) for mode in players}
        by_size[size] = {**timing, "speedup": timing["serial"] / timing["batch"]}
    result = dict(positions=len(positions), samples=args.samples, repeats=args.repeats,
        timing_seconds=totals, speedup=totals["serial"] / totals["batch"], by_remaining_tricks=by_size,
        mismatches=0, measurements=rows)
    path = Path(args.out); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as f: json.dump(result, f, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != "measurements"}, indent=2))


if __name__ == "__main__": main()
