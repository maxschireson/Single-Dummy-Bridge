# Gen 9 signals: played-board runs for a box

> sam, 12 November 2026. Work in progress; for will's queue (G9-W5) and g9's box order. Nothing
> here is an arena cohort.

Both runs use `scripts/gen9_match.py` (duplicate, fork-free, fresh deals; deals are a function of
seed and index, so two matches with the same seed play the same deals) with a bots file that
merges the Gen 8 prototype entries and the signal bots:

```bash
python3 -c "import json; a=json.load(open('configs/gen8-proto-bots.json')); b=json.load(open('configs/gen9-signal-bots.json')); \
a.update({k: v for k, v in b.items() if not k.startswith('_')}); json.dump(a, open('/tmp/gen9-signal-run-bots.json', 'w'))"
B="--source CAPSULE/recovery --bots /tmp/gen9-signal-run-bots.json --workers 8"
```

Measured in a sandbox: 129 boards an hour per worker for `cp-std-100~8p-32` (1 board, 2 tables).
On an 8-core box, about 1,000 boards an hour, so 1,600 boards is about 1.6 hours a match.

## E9-4 part 2: the signal reader against carding bots (about 3.2 box-hours)

Same deals for both matches (seed 94). The difference in IMPs a board, board by board, is the result.

```bash
python3 scripts/gen9_match.py $B --pair r9-32~c-std-80 --deals 1600 --seed 94 --out RUNS/e9-4-r9
python3 scripts/gen9_match.py $B --pair 8x-32~c-std-80 --deals 1600 --seed 94 --out RUNS/e9-4-8x
```

`r9-32` is `8x-32` told each carding bot's scheme. Its `models` block states the bot's honesty (0.8);
E9-4 part 1 says a reader at 0.7 to 0.8 reads these bots as well as any.

## E9-6 part 2: designed signals for the house pair (about 4.8 box-hours)

```bash
python3 scripts/gen9_match.py $B --pair cp-std-100~8p-32 --deals 1600 --seed 96 --out RUNS/e9-6-vs-8p
python3 scripts/gen9_match.py $B --pair cp-std-100~r9p-32 --deals 1600 --seed 96 --out RUNS/e9-6-vs-reader
python3 scripts/gen9_match.py $B --pair cp-att-100~r9p-32 --deals 1600 --seed 96 --out RUNS/e9-6-att-vs-reader
```

Part 1 (`reports/gen9-signal-pair-2026-11-12`) found the leak to a declarer who knows the scheme
larger than the defence's gain, in nats, and `8p-32` misled by the spots it reads with the house net.
So the second and third matches decide the question; the first is kept for comparison. About 4.8
box-hours for all three; if only two fit, run the second and the third.

`cp-std-100` is `8p-32` whose defenders signal standard count and attitude and fourth-best leads at
honesty 1 and read each other by them. `r9p-32` is `8p-32` told that scheme (its declarer reads the
signals: what they leak). The comparison against BEN needs a box with BEN servers and is not here.

## Results

Each run's `summary.json` and `results.jsonl` (and `--episodes` if the records are wanted for
reading-gain checks) go to `transfer/gen9-<experiment>-<box>-<date>`, named in the experiment's log.
