# Gen 7 pre-arena test feed: azure2

Dashboard publication of the pre-7 test match on azure2: Gen 7 standard (`7s-32`) against Gen 6
fast (`6-32`), played 12 November 2026 before the Gen 7 arena launch. Frozen: the match has
finished and this branch will not change.

- Source run: `pre7-7s-vs-6f-azure2/` on `transfer/pre7-test-azure2-20261112` at `688c9bc2337508282a1253e7263698c461529a47` (episodes, receipts,
  manifest with every bot's exact settings). Guide: `docs/pre7_test_2026-11-12.md` on
  `feature/gen7-prepare-slice-20261112`.
- Exported read-only with `ops/export_gen5.py` (code from `feature/gen7-prepare-slice-20261112`);
  every table was replayed and its score checked. The run was not changed. The exporter needs a
  `heartbeat.json` and accepts a `statistics-policy.json`; both were written only in the
  exporting copy (8 workers; retired, target = completed boards, title).
- Settings: as phase 1's `7s-32` except tree `trust` 0.25 (phase 1 uses 0.3). On Max's
  instruction (12 Nov 03:05 UTC) the dashboard does not distinguish the two.
