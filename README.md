# E9-16 sandbox pilot: `8r-32~8p-32`, 400 boards (will, 12 Nov 2026)

A transfer branch, never merged into source. g9 asked for it at 15:15 UTC: a played figure for Max's leakage question before the box runs E9-16. It is a pilot and not part of the result. The box job uses seed 916; this run used 917.

- **Source:** `feature/gen9` at `491c7f7`, with DDS built and the 13 nets restored by `scripts/run_tests.py`'s `restore_models`.
- **Capsule:** the recovery capsule of `arena-gen6-gen7-capture-feed` at `8833c62`, without its episodes.
- **Command:** `BRIDGE_DDS_CACHE= python3 scripts/gen9_match.py --source <capsule>/recovery --bots configs/gen9-proto-bots.json --pair 8r-32~8p-32 --deals 400 --seed 917 --workers 2 --out <dir>`, with one thread per process.
- **How it ran:** in 9-minute pieces from 15:21 to 17:23 UTC, on a 2-CPU sandbox. The match resumed from `results.jsonl` each time, and each of deals 0 to 399 was played once.
- **Result (`summary.json`):** `8r-32` scores **+0.17 +- 0.17 IMPs a board** over 400 boards, with 72 won, 59 lost and 269 flat. Common and native are the same, because both bots bid with the same net. The match cost 33.6 CPU-seconds a board.
