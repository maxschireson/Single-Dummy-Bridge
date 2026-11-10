# 5R192 versus 5R32: opening-lead cost and attribution

Analysis of frozen arena commit 8f386190b57714f94c904c922cbcdf36ab7791a2 (snapshot generated 2026-11-10 16:42:46 UTC). These are 5R, not ties-only 5RZ. All 2,030 compressed episode blobs were verified against their recorded Git blob SHAs. The head-to-head subset contains 147 distinct deal families, one passed out. Only common-auction root tables are included; native-auction duplicates and recursive audit continuations are excluded.

## Measured cost

Each played deal has two tables with swapped partnerships. Each bot is charged for 52 decisions across the pair: one opening lead and 51 subsequent plays. Means below are wall seconds charged to that bot per paired deal on the source host.

| Stage | 5R32 | 5R192 |
|---|---:|---:|
| Opening lead | 1.2503 | 9.8359 |
| All subsequent decisions | 3.3339 | 8.9280 |
| Total | 4.5842 | 18.7639 |

Opening lead is 52.42% of 5R192's own decision time and 60.55% of the extra decision time relative to 5R32. CPU times give nearly identical shares (52.53% of 5R192 CPU). Mean actual DDS worlds on lead: 29.59 and 189.99.

Replacing only the 192 lead with a 32 lead would arithmetically save about 8.59 seconds, or 45.76% of 5R192's own decision time (36.77% of total time charged to both bots in this pairing), IF later play costs remained unchanged. This is an estimate, not a measured hybrid run; changed leads alter later positions and costs.

## Existing outcome evidence

5R192 scored +21 IMP across the 147 paired deals: +0.14286 IMP/deal, standard error 0.27491; total-equivalent SE 40.41 IMP. This small frozen cohort does not establish the overall strength advantage.

Among 146 played deals:
- Same opening card: 88 deals, +2 IMP for 5R192.
- Different opening card: 58 deals, +19 IMP for 5R192.

The concentration on different-lead boards is descriptive, not causal attribution. Later search budgets differ in both groups, and the different-lead group is selected by the bots' choices. Do not claim that 19/21 of the advantage was caused by the lead. Recorded Gen3-reference forks compare selectors using the same PIMC details and do not provide the missing 32-versus-192 opening-lead counterfactual.

## Efficient attribution experiment

First compare 32-on-lead/192-afterward with 192-throughout, on identical held-out deals, auctions, contracts, network weights, policy threshold, and fixed opponent. Swap partnerships and pair results by deal. This estimates the practical cost of making only the opening lead cheaper.

For a full two-factor experiment, also run 32-throughout and 192-on-lead/32-afterward. Compare the lead upgrade under both continuation budgets, and the later-play upgrade under both lead budgets. Report the interaction; an opening lead can be valuable only if subsequent play exploits it. If allocating total IMP value between stages, use scores against one fixed comparison result before calculating differences of mean IMP performance; directly summing pairwise IMP conversions is not generally additive.

Opening lead selection only needs to be run once per budget per deal. Reuse identical-lead continuations within each continuation setting, with randomness keyed to the observed position so different sample consumption on lead cannot shift later random streams. Replay distinct leads under matched continuation policies, using actual single-dummy play. Count lead agreements as zero lead effect and retain them in the denominator. Cluster uncertainty by deal family. Report IMP/deal, decision time, and IMP gained per additional second; separate suit and notrump contracts.

A true-deal double-dummy lead comparison can screen tactical lead losses cheaply but does not measure actual single-dummy playing strength. No new lead experiment or arena change was launched by this analysis.
