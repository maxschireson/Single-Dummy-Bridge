# Gen 6 BEN matchup correction — collector handoff

User direction (2026-11-11): BEN must play Gen 6 medium, not fast. Preserve the few fast-versus-BEN boards as archived data, but exclude them from the dashboard.

## Changes already pushed

- Collector branch: `codex/gen6-independent-collector-20261111`.
- Commit `ea356cf7f904b10d6bb5b47d93a306e7de6fa268` updates `configs/round6-independent.json`: replace `6-32~ben` with `6-256~ben`, weight 3 of 20 (15%), and add audit reference `6-256: 3`.
- All other allocation weights are unchanged: fast vs Gen5 8, fast vs medium 3, fast vs Gen3/2/1 2 each.
- Medium remains 256 samples before the compatible-layout cutover at trick 6; BEN remains 16 samples. The common bidder remains Gen6 fast.
- Dashboard branch: `gh-pages`.
- Commit `83de492a3938b54fcf3d93b290bc3f65bd2d7c9f` excludes normalized `6-32~ben` records from report rows and collection rates in `arena/reporting.js`. This covers both orientations, common/native results, differences, curves, and report totals.
- The latest dashboard also contains subsequent timing-filter changes. Preserve the latest branch contents; do not overwrite them with this handoff's older commit.
- Verified the published plan and dashboard filter again when writing this handoff. Synthetic checks passed for exclusion in both orientations and retention of medium/BEN results.

## Required pickup in the running collector environment

This chat has NOT stopped or restarted the live collector. A GitHub plan edit does not alter its already frozen manifest.

1. Fetch the collector branch and inspect the configuration change above; integrate it into the actual launch configuration used by each affected Gen6 collector.
2. Drain affected workers and prevent the old watchdog from restarting the old allocation during cutover. Preserve completed episodes, receipts, corpus, and frozen manifest.
3. Freeze a new manifest/cohort for the corrected allocation using the established cutover workflow. Do not mutate the old frozen manifest, relabel fast games as medium, or mix receipts from different manifests. Preserve valid completed games from other matchups.
4. Keep fast/BEN records available as archived raw data. They must stay excluded from current and all-generation dashboard aggregates.
5. Start the corrected collector with medium/BEN and the existing allocation weights. Verify its actual runtime bot identity, 256-sample setting, trick-6 list cutover, and BEN16 configuration.
6. Publish synchronized score/replay snapshots. If the cohort identity or feed changes, update the dashboard registration using the latest gh-pages base, retaining other streams and the fast/BEN exclusion.
7. Check that medium/BEN results appear and fast/BEN results do not; verify board totals, common/native scores, paired differences, rates, and timing. Preserve the newer per-record timing exclusion already present on gh-pages.
8. Post a follow-up status to GitHub containing old/new manifest identities, archive counts, effective runtime settings, launch state, feed commit, first verified medium/BEN board count, and any blockers. Do not mark the live switch complete based only on this configuration commit.

The same user correction applies to any other Gen6 collection stream still scheduling fast against BEN. This handoff changes the independent Codex launch plan; owners of other streams must inspect and correct their own frozen configurations.
