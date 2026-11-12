# E9-4 part 1: what reading a declared carding scheme is worth

Gen 9 research (sam, signals), 12 November 2026. Experiment file: `experiments/E9-4.md` on
`team/gen9`. Kind of evidence: **prediction** (gain in the true layout's log weight); no match was
played. Nothing adopted.

**Method.** `scripts/gen9_reading_gain.py` on `arena-gen7-phase1-azure1-feed` at `f9dad79`, the
first 300 main tables (296 usable), house bots defending. For each cell (scheme × honesty) the
defenders' spot cards and opening leads are drawn again by the carding bot's rule
(`signals.SignalModel`, the defender's true hand, within the recorded tie set), and the two cards'
order of play is swapped for the rest of the board; a swap that would change a trick's winner is
undone (11 to 20 of about 1,500 per cell; no table dropped). Declarer's decisions in tricks 1 to 6
(3,153 per cell) are then scored as `scripts/gen8_play_info.py` scores them: the gain in nats of
the true layout against a pool of 256 auction-weighted layouts, from the defenders' plays so far.
Standard errors are clustered by table. Every cell uses the same deals, decisions and pools.

**Readers.** `net 0.3`: Gen 8 reading an unknown opponent (the policy net on the card, factor
0.3). `net 1`: the house net in full. `class`: the net on the class of the card only (spots
ignored). `signal reader`: class term plus the signal term (`SignalPlayer.signal_row`) with the
cell's scheme, assuming honesty h. `h 0` knows which spots the scheme plays but not what they
say, so "reader minus h 0" is what the facts are worth.

## Result

| Cell (scheme, honesty) | Gen 8 (net 0.3) | House net in full | Class only, phi 1 | Signal reader, phi 1, true h | Reader minus Gen 8 | Of which the facts (minus h 0) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| std-100 | +0.195 ± 0.019 | -0.019 ± 0.062 | +0.320 ± 0.040 | +1.100 ± 0.086 | +0.905 ± 0.083 | +0.571 ± 0.063 |
| std-80 | +0.184 ± 0.019 | -0.053 ± 0.064 | +0.309 ± 0.041 | +0.901 ± 0.071 | +0.717 ± 0.067 | +0.374 ± 0.047 |
| std-50 | +0.188 ± 0.019 | -0.043 ± 0.063 | +0.304 ± 0.041 | +0.675 ± 0.058 | +0.487 ± 0.053 | +0.159 ± 0.029 |
| std-0 | +0.182 ± 0.021 | -0.077 ± 0.071 | +0.305 ± 0.042 | +0.508 ± 0.049 | +0.326 ± 0.041 | +0.000 ± 0.000 |
| ud-100 | +0.172 ± 0.022 | -0.111 ± 0.073 | +0.327 ± 0.040 | +1.136 ± 0.075 | +0.964 ± 0.073 | +0.630 ± 0.061 |
| ud-80 | +0.184 ± 0.020 | -0.085 ± 0.068 | +0.321 ± 0.041 | +0.969 ± 0.065 | +0.784 ± 0.062 | +0.461 ± 0.044 |
| ud-50 | +0.179 ± 0.021 | -0.086 ± 0.069 | +0.325 ± 0.040 | +0.687 ± 0.054 | +0.508 ± 0.049 | +0.188 ± 0.027 |
| std35-80 | +0.195 ± 0.020 | -0.027 ± 0.065 | +0.315 ± 0.040 | +0.898 ± 0.069 | +0.703 ± 0.065 | +0.367 ± 0.046 |

- **Reading the declared scheme is worth +0.49 to +0.96 nats per declarer decision over Gen 8**
  at honesty 0.5 to 1, and the part that comes from the facts rises with honesty: +0.16, +0.37,
  +0.57 for standard at 0.5, 0.8, 1; +0.19, +0.46, +0.63 upside-down. At honesty 0 it is 0.000 by
  construction (tested).
- **Upside-down and standard are read equally well**, and third-and-fifth leads (`std35-80`) are
  worth as much as fourth best (`std-80`): +0.70 against +0.72.
- **Two gains that do not need the facts.** (1) Reading the class at factor 1 instead of the card at
  0.3: +0.12 to +0.16. The class choices here are the house bots' own, which the net knows, and
  the net's misreading of foreign spots is what made Gen 8 discount the whole card. (2) Knowing
  which spots the scheme plays (extremes) even at h 0: about +0.2 more. The second depends on the
  bot's rule playing only the highest or lowest spot; a real player's middle spots would cut it.
- **The house net read in full is worse than Gen 8's discount** on these defenders (-0.21 to
  -0.28 against `net 0.3`), as Gen 8's calibration found for the fixed-carding types.
- **Later tricks gain more:** reader minus Gen 8 is +0.76 in tricks 1 to 4 and +1.21 in tricks 5
  and 6 for `std-100` (`tables.txt`).

**What a wrong honesty costs** (signal reader at factor 1, minus Gen 8; rows: the bots' true
honesty; columns: the honesty the reader assumes):

| Cell | True h | Assume 0 | 0.5 | 0.8 | 0.9 | Assume the true h |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| std-100 | 1 | +0.33 ± 0.04 | +0.78 ± 0.06 | +0.92 ± 0.07 | +0.93 ± 0.07 | +0.90 ± 0.08 |
| std-80 | 0.8 | +0.34 ± 0.04 | +0.67 ± 0.05 | +0.72 ± 0.07 | +0.68 ± 0.07 | +0.72 ± 0.07 |
| std-50 | 0.5 | +0.33 ± 0.04 | +0.49 ± 0.05 | +0.39 ± 0.07 | +0.27 ± 0.08 | +0.49 ± 0.05 |
| std-0 | 0 | +0.33 ± 0.04 | +0.16 ± 0.05 | -0.23 ± 0.08 | -0.53 ± 0.10 | +0.33 ± 0.04 |
| ud-100 | 1 | +0.33 ± 0.04 | +0.80 ± 0.05 | +0.95 ± 0.06 | +0.97 ± 0.06 | +0.96 ± 0.07 |
| ud-80 | 0.8 | +0.32 ± 0.04 | +0.71 ± 0.05 | +0.78 ± 0.06 | +0.77 ± 0.07 | +0.78 ± 0.06 |
| ud-50 | 0.5 | +0.32 ± 0.04 | +0.51 ± 0.05 | +0.43 ± 0.06 | +0.33 ± 0.07 | +0.51 ± 0.05 |
| std35-80 | 0.8 | +0.34 ± 0.04 | +0.67 ± 0.05 | +0.70 ± 0.06 | +0.66 ± 0.07 | +0.70 ± 0.06 |

Assuming more honesty than there is costs much more than assuming less. Against bots at honesty 0,
assuming 0.9 loses 0.86 nats against the right reading; against bots at honesty 1, assuming 0.5
loses 0.12. Against honest bots 0.9 reads slightly better than 1, because the bot signals among its
tied cards and the reader assumes the whole class (8.5% of plays, E9-3). So honesty should start
low and be learned (G9-S5's learning curve, next).

**Limits.** Prediction evidence: nobody reacts to the signals (partner does not read them;
declarer's recorded choices stand), so this is what the reading is worth to the layout weights,
not in IMPs; E9-0 (g9) is to convert nats to IMPs, and part 2 plays the boards. The class choices
are the house bots', which favours the class term at factor 1; against a foreign player whose
class choices the net does not know, the class factor should be lower. One feed.

**Reproduce.** `python scripts/gen9_reading_gain.py EPISODES --source CAPSULE/recovery --tables 300
--out rows.jsonl` (about 25 minutes on two cores) and `python scripts/gen9_reading_gain_report.py
rows.jsonl`. The capsule is the feed's own `recovery/` folder (`manifest.json`, `artifacts/`);
`pip install h5py`.
