# Gen 4 component isolation

Gen 4 loses roughly one IMP per paired board to Gen 3 in both original and independent supplemental cohorts. The loss persists with common Gen 4 auctions, so bidding does not explain the main regression.

Two frozen variants isolate the cardplay changes:

| Bot | Belief | Policy | Native bidder |
| --- | --- | --- | --- |
| Gen 4p | Gen 3 | Gen 4 audited IMP | Gen 3 |
| Gen 4b | Gen 4 | Gen 3 | Gen 3 |

Both use 32 samples, a 0.125-trick eligibility window, and zero exploration. Model hashes and identities are in `configs/gen4-component-bots.json`. These are combinations of existing checkpoints; no new training occurred.

The separate `gen4-components-20261109` cohort has 10,000 fresh deals, excluding all families in the earlier 10,000-deal supplemental corpus. Each shuffled ten-board block contains three 4p–3, three 4b–3, and one each of 4p–4b, 4p–4, 4b–4, and 4–3. Every comparison uses two rooms and both common-v4 and native bidding regimes, with identical trajectories reused. Existing frozen cohorts are unchanged. The new feed is `arena-components-feed`; source is `research/gen4-components`.

The policy implementation is a suspect, not a proven cause. Its IMP output started at zero and replaced the inherited action-ranking output, which is retained only as an auxiliary training head. Selected validation MSE improved from 2.459157589 to 2.459101836, a family-mean improvement of 0.000055729 with SE 0.000185622 (0.30 SE). This is essentially no validated predictive gain. On 965 supplemental episodes, it changed 31,891 of 46,158 eligible Gen 4 decisions (69.1%). Root one-move audits were inconclusive: the family-normalized gain was -0.0144 IMP per audit, SE 0.0154. Budget-dependent audit omissions and fixed continuation limit interpretation.

A separate 500-family diagnostic replays one outcome-independent, family-hash-selected root room per deal. It replaces only the focal partnership's policy or only its belief while holding the opponent, auction, sample budget, and random stream keys fixed. Eight unchanged baseline replays reproduced every card and final score exactly. These are matched substitutions against mixed opponents, not direct two-room arena matchups; their data must not be pooled into the arena. All 500 deals completed. Restoring only the old policy (4b) gained 83 IMPs, +0.166 per deal, SE 0.1748, descriptive 95% CI [-0.177, +0.509]. Restoring only the old belief (4p) gained 64 IMPs, +0.128 per deal, SE 0.1183, CI [-0.104, +0.360]. Neither isolates the regression statistically. Results and code are in `reports/gen4-diagnostic-500`. The component interaction and opponent mix remain unresolved. The direct 4p/4b arena now supplies the intended comparison.

## Recovery

Prepare a new run with `scripts/prepare_component_arena.py --source SOURCE_RUN --out NEW_RUN`. Run `scripts/run_supplemental_arena.py --run NEW_RUN --workers 4 --seconds 86400` with single-threaded BLAS. Only one collector may hold the writer lock. Stop markers drain the job; never overwrite frozen manifests. Run `scripts/publish_component_feed.js` in the authenticated functions runtime to publish roughly once per minute. It writes only its dedicated branch. Completed episodes are immutable and resumed by index.

Multi-character IDs use explicit pair members and `~`-separated public keys, e.g. `4p~3`; legacy pair keys such as `43` remain valid. The dashboard selector links to the component cohort at `arena/?source=components`, and all IMP/count links retain cohort identity and snapshot cutoffs.

Validation: 17 unit tests cover component artifact selection, unchanged native bidders, immutable source specs, multi-character scheduling, statistical signs, auction reuse and the existing arena behaviors. Published trajectories are replay-validated before export.
