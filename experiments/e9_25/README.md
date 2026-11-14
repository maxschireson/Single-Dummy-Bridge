# E9-25: the 0.9 threshold against BEN defenders (g9, Gen 9)

Registration: `team/gen9:experiments/E9-25.md` (from E9-24, `reports/gen9-sid-weights-2026-11-13`). Positions are
declarer-side decisions at 8 and 7 cards on native tables of the Gen 8 BEN 64 feeds (`arena-gen8-azure3-ben64-*`),
shape level. For each position, layouts are weighted two ways:

- `b`, the hand-fit scorer for both hidden seats;
- `g`, Gen 9's reading, where a seat BEN plays is read by replaying BEN's own bidding net
  (`bridge_harness/cards/replay.py` `ReplayReader`).

The conditional claims' certified sets are then compared against the actual layout. The control is the same feeds'
house-defended positions.

| File | What |
| --- | --- |
| `e925_positions.py` | Positions from feed board files, with who defended. |
| `e925_study.py` | Weights, cells and floors per position. One JSON line each; the run resumes. Without `--ben` it is a dry run in which both weightings are the scorer's. |
| `e925_report.py` | The three registered predictions. |
| `cells/` | Unchanged copies of `experiments/sure_tricks/cells/{arena_positions,belief,celllib,pipeline,study}.py` and `cells.cpp` from `research/conditional-claims-20261113` at `baa062c`, so a box job needs one checkout. |

## Running

The scorer is the feeds' own: `artifacts/gen6/scorer.npz` in the capsule, SHA-256 `56e6444079d1…`. `BEN.keras` is BEN's
GIB-BBO-8742 bidding net, SHA-256 `b0dff3df…`; on azure4 it is the copy BEN 64 serves from (path to be confirmed by
will).

```
g++ -O2 -std=c++17 -o experiments/e9_25/cells/cells experiments/e9_25/cells/cells.cpp
python3 -I experiments/e9_25/e925_positions.py experiments/e9_25/cells positions.jsonl 8,7 shards/*.json
python3 -I experiments/e9_25/e925_study.py positions.jsonl ben_defends-8.jsonl 8 ben_defends \
    --cells experiments/e9_25/cells --repo . --scorer SCORER.npz --ben BEN.keras --ben-sha SHA --limit 750
python3 experiments/e9_25/e925_report.py OUT_DIR
```

## Checked in the sandbox

- **Positions.** Two board files of `arena-gen8-azure3-ben64-1-feed` gave 350 native tables and 642 positions: 337 with
  BEN defending, 305 with house bots defending.
- **Study.** A dry run on 3 positions, without BEN, completed.
- **BEN's replay (14 Nov).** The first box run (02:47 UTC) failed loading BEN's net: `BenLstmBidder` read the output
  layer under the house bidders' name (`layers/dense`), and BEN saves the same 40-way softmax Dense inside
  TimeDistributed (`layers/time_distributed/layer`). Fixed in `bridge_harness/system_bidders.py`, with
  `tests/test_ben_lstm_layout.py`. Checked here with BEN's file fetched from BEN's public repository (SHA-256 matches
  the pin above; the net is not kept in this repository): the other layers and settings are the house bidders'
  (193 inputs, three 256-unit LSTMs, batch-norm epsilon 0.001); on 2,000 random deals BEN's net opens 1NT only on 15 to 17
  points, passes as dealer only with 11 or fewer, and opens as the house bidder does on 99.2% of deals; the study ran
  on 3 positions with the BEN replay.
