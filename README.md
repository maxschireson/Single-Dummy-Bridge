# The arrival run (G9-D6), azure4, 12 to 13 November 2026

This is a transfer branch: records only, never merged into source. The box published the run to `transfer/gen9-d6-arrival-azure4-20261112` (e26a68b); this branch holds the same records and the page.

- **`report.md`: the page,** items 1 to 6, each beside the prediction registered before the run. It was regenerated from `control/` with `scripts/arena9.py report --note` at 698679e, which adds the "known and accepted" lines (sam's 8be31d6; the stop and the resume). `report-as-run.md` is the page the run wrote itself; it lacks those two lines and is otherwise the same.
- **`control/`:** the registry log, the six epoch manifests (epoch 6 is opened, not played), the rows and experience envelopes of each epoch, the ratings, the snapshots, and the arrival distances.
- **`results.jsonl`:** all 6,200 board rows. Floor rows carry `reading` (item 6).
- **`replay.json`:** item 5. **`job.json`:** the box job.

**Source.** `feature/gen9-arena-arrival`. Epochs 1 to 3 were opened under 8cb0348. The run stopped at 17:53 UTC on 12 Nov in epoch 3, on board 524569 of `8p-32~guest-a`: guest-a's rule bidder raised on the house net's 3NT opening. It resumed in the same folder at 698679e, released by will at 18:55; the page's notes say why the boards already played stand.

**Not produced:** the play factor chosen (item 2). The pipeline writes no `play.info` statistic, so that column is empty.
