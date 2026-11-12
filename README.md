# Pre-7 test data: azure2

Gen 7 standard candidate (`7s-32`: policy v4, play weights, net tie-break, tree at tricks 3 to 6 with
the stake rule at `path` 0.5 and 3 tricks) against Gen 6 fast (`6-32`), played on test machine azure2
from 12 November 2026 while the arena was still on Gen 6.

**A test run, not an arena cohort.** This branch is not a feed and its boards are not pooled into
arena scores.

- Run folder: `pre7-7s-vs-6f-azure2/` with `manifest.json`, `plan.json`, `corpus.jsonl`,
  `source-indices.json`, `state.json`, `episodes/`, `receipts/` and `failures/`.
- Deals: positions 5627 to 11253 of the 22,508 unplayed deals of the
  `arena-gen6-gen7-capture-feed` capsule at `8833c62`. The other machines play other blocks.
- Workers: 8, each held to one thread. Source commit: `95b8380`.
- Sibling branches: `transfer/pre7-test-azure1-20261112` to `transfer/pre7-test-azure4-20261112`.
- Guide, settings and limits: `docs/pre7_test_2026-11-12.md` on `feature/gen7-prepare-slice-20261112`.

Written by `ops/publish_test_run.py` every ten minutes while the run is live.
