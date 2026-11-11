# Auction belief: ceiling tests, joint-net prototype, hand-fit scorer, hand-type classes

**Status: research prototype. Not the final package for the Gen 6 cutover.** Measured on the Gen5 bidder and the v5 belief net. No arena bot uses anything here, nothing under `bridge_harness/` or `scripts/` depends on it, and the nets must be retrained for any other bidder. Do not treat these files, weights or results as cutover inputs.

Results, method and limits:

- Opening lead: [reports/auction_belief_lead_2026-11-10.md](../../reports/auction_belief_lead_2026-11-10.md)
- The play after the lead: [reports/auction_belief_play_2026-11-11.md](../../reports/auction_belief_play_2026-11-11.md)

Trained nets (run `python restore.py` in each folder to rebuild the weights):

- `models/cardplay/joint-auction-belief-lead-v0-2026-11-10/` joint net for the opening leader (`joint_lead_v0.npz`)
- `models/cardplay/hand-fit-scorer-v0-2026-11-11/` hand-fit scorer for the play (`hand_fit_v0.npz`)

Set `SDB_FEED` to the arena feed's `recovery` folder before running anything here. The run commands are at the end of each report.

Layout-selection test (which layouts to solve; about 90 s per table per core):

```bash
export SDB_FEED=/path/to/feed/recovery
(cd ../../models/cardplay/hand-fit-scorer-v0-2026-11-11 && python restore.py)
S=../../models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz
python select_layouts.py $S out/sel_0.jsonl 300 326 2 0    # offset 1 in a second process
python analyze_select.py
```
