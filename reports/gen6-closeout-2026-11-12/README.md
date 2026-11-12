# Gen 6 closeout results (12 November 2026)

**Question.** How did Gen 6 score against each opponent over its whole arena run?

**Method.** `python scripts/generation_results.py --generation 6 --out results.json`, run
12 November 2026 ~03:05 UTC. It reads the 18 Gen 6 sources in the dashboard registry
(`gh-pages:arena/gen6-sources.json`), loads each score snapshot and replay index at its
registered revision (retired) or branch head (live), and applies the dashboard's rules:
records after the snapshot cutoff dropped; BEN (32) and the two accidental fast-vs-BEN16
cohorts excluded; one observation per deal family and matchup, earliest completion kept.
Common = Gen 6 bidder at all four seats; native = each side's bidder; bidding = native −
common on the same boards.

**Result.** 31,935 counted boards from 31,954 observations. The table and its reading are on
the [Gen 6 page](../../docs/generations/gen6/README.md#results); per-source revisions and full
statistics (wins/ties/losses, standard errors) are in [results.json](results.json).

**Limits.** Normal-approximation 95% intervals, unadjusted for repeated monitoring. Pairs
were collected at different times, mixes and deal sets, so comparisons across rows (for
example fast vs BEN against medium vs BEN) are not paired tests. Live sources were read at
their heads; rerunning later will add Gen 6 self-play boards but should not change the
scored pairs, which had stopped. Feeds absent from the registry are not counted.
