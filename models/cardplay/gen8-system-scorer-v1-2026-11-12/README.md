# System-aware hand-fit scorer v1 (12 November 2026)

**Gen 8 candidate artifact. No arena bot uses it until Max launches Gen 8.**

`system_scorer_v1.npz` is the Gen 6 hand-fit scorer (`hand_fit_v0`, the `scorer` of every Gen 6, 7 and 7.1 bot,
sha256 `56e6444079d1451ada7730e7d4fa5764caee766102af0386831ed73c42245e73`) with one more table of call readings, for the project's own rule system
(`rules-precision`: `bridge_harness/rule_bidder.py`, rules r3 with judgement j1 ("r4"), settings
`configs/rule-systems/precision-r4.json`, identity `f50e95de93ac0dbeef213be965d966c75693932b1f039128d46b752321e6164c`). A player that declares each side's system (`bridge_harness/system_nets.py`,
`Gen6Player.seat_table`) reads a side's calls with that side's table.

- **Nothing declared, the house system, or a system the file does not hold: the base scorer, exactly.** Only the new
  system's table was trained (`--only rules-precision`); every other array is the base file's. Checked at packaging on
  300 random auctions and hands: largest difference 0.0e+00.
- Trained with `scripts/train_system_scorer.py` (20083 steps, best at 14739, declared view only) on
  60000 random deals bid at three kinds of table by `scripts/gen_system_fit.py` (seed 6301): the rule
  system at both sides, and against the house bidder (`house-gen6`) each way round.

Validation (8,000 other deals, seed 6302). Loss is cross-entropy on "would this hand have made this seat's calls";
"true" is the share of true hands rated above one half. "Unknown" is the same file with nothing declared, which is
how a bot without this scorer reads these auctions.

| North-South | East-West | declared: loss | true | unknown: loss | true |
|---|---|---|---|---|---|
| rules-precision | rules-precision | 0.143 | 0.918 | 1.312 | 0.575 |
| rules-precision | house-gen6 | 0.142 | 0.909 | 0.728 | 0.743 |
| house-gen6 | rules-precision | 0.145 | 0.902 | 0.709 | 0.748 |

`python restore_model.py` rebuilds the file from its parts and checks every hash. `metrics.json` is the trainer's
report. A new version of the rules, of their settings or of the trick estimate is a new system identity and needs a new table.
