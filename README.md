# Gen 9 cohort inputs (13 November 2026)

A transfer branch: never merged into source.

- `played-families-20261113.json.gz`: the 85,910 canonical deal families (`bridge_harness.bidding_env.deal_key(hands, True)`)
  of every record on the dashboard's 111 registered sources (gh-pages `arena/gen6-sources.json` merged over the list
  in `arena/reporting.js`), collected at 04:26 UTC by `scripts/arena_ladder.py collect` (branch `feature/gen9-ladder`).
  sha256 `ac5243e11112bf68fbc6a8c8700cf6b36ab829a2348f5925c5fcf721c567333c`.
  Used by `ops/prepare_gen7_alpha.py --fresh ... --played` on `feature/gen9-cohort` so that the Gen 9 cohort's fresh
  deals contain none already played (docs/gen9/cohort.md).
