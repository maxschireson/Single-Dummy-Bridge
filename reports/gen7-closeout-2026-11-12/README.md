# Gen 7 closeout results (12 November 2026)

**Question.** How did Gen 7, in its two versions (7.0 with policy net v4, 7.1 with v4.1), score against each
opponent over its arena run?

**Method.** `python scripts/generation_results.py --generation 7 --fetch gh --out results.json`, run 12 November
2026 at 18:04 UTC and again at 18:07 with the same counts. It reads the 53 Gen 7 sources in the dashboard registry
(`gh-pages:arena/gen6-sources.json`), loads each score snapshot and replay index at its registered revision (14
retired sources) or branch head (39), and applies the dashboard's rules: records after the snapshot cutoff
dropped; BEN (32) excluded; one observation per deal family and matchup, earliest completion kept. Common = the
Gen 6 bidder at all four seats; native = each side's bidder; bidding = native − common on the same boards. For this
run the script's actor order was brought up to the dashboard's (`71s-32` and the Gen 8 actors added in front), which
is what names and signs a pair.

**Result.** 21,601 counted boards from 22,214 observations. The table and its reading are on the
[Gen 7 page](../../docs/generations/gen7/README.md#results); per-source revisions and full statistics
(wins/ties/losses, standard errors) are in [results.json](results.json).

| Pair | Boards | Common auction, mean ± standard error | Won / tied / lost |
| --- | ---: | --- | --- |
| `71s-32` vs `7s-32` | 5,507 | −0.071 ± 0.036 | 552 / 4,424 / 531 |
| `71s-32` vs `6-32` | 2,234 | +0.302 ± 0.064 | 396 / 1,626 / 212 |
| `71s-32` vs BEN (64) | 4,623 | +0.008 ± 0.056 | 1,169 / 2,625 / 829 |
| `71s-32` vs BEN (16) | 378 | −0.159 ± 0.215 | 101 / 204 / 73 |
| `7s-32` vs `6-32` | 3,083 | +0.262 ± 0.058 | 527 / 2,255 / 301 |
| `7s-32` vs `5RZ32` | 1,319 | +1.139 ± 0.114 | 470 / 703 / 146 |
| `7s-32` vs Gen 1 | 1,319 | +2.238 ± 0.125 | 666 / 534 / 119 |
| `7s-32` vs BEN (16) | 1,274 | +0.095 ± 0.119 | 357 / 700 / 217 |
| `7s-32` vs BEN (64) | 684 | +0.069 ± 0.153 | 177 / 386 / 121 |

**Where each row's boards come from** (counted boards by group of feeds):

| Pair | Groups |
| --- | --- |
| `71s-32` vs `7s-32` | 19bbdce5 1,459; independent 1,444; Codex 1,316; azure2 726; azure1 562 |
| `71s-32` vs `6-32` | independent 846; 19bbdce5 730; Codex 658 |
| `71s-32` vs BEN (64) | azure3 lanes 4,345 (first pool 2,928, second 1,417); independent 278 |
| `71s-32` vs BEN (16) | independent 378 |
| `7s-32` vs `6-32` | pre-arena test 1,637; Azure phase 1 870; Codex 343 (phase 1 188, self-play mix 155); independent 217; extra 13; azure2 self-play mix 3 |
| `7s-32` vs `5RZ32` | Azure phase 1 995; Codex 188; independent 101; cloud 23; extra 12 |
| `7s-32` vs Gen 1 | Azure phase 1 995; Codex 188; independent 102; cloud 22; extra 12 |
| `7s-32` vs BEN (16) | azure2 lanes 1,195; independent 79 |
| `7s-32` vs BEN (64) | azure3 lanes 606; independent 78 |
| `71s-32` self-play (628) | azure1 628 |
| `7s-32` self-play (552) | Codex 314; independent 230; azure2 8 |

**Limits.**

- Normal-approximation 95% intervals on the generation page, unadjusted for repeated monitoring. The 7.1 against
  7.0 pair was the subject of a stopping rule and was read many times.
- Pairs were collected at different times, mixes and deal sets, so comparisons across rows (7.0 against Gen 6 with
  7.1 against Gen 6, either against BEN) are not paired tests.
- Feeds absent from the registry are not counted. At 18:04 UTC that left out `arena-gen7-1-mix2-azure1-feed` (381
  boards) and the `arena-gen7-1-fresh3-azure3-ben64-*-feed` lanes (105 boards), both drained at the switch to Gen 8,
  and, by design, the three Gen 7.1 sets closed on 12 November at 06:32 to 06:39 UTC because policy net v4.1 was
  trained on their deals (393 boards).
- 1,637 of the `7s-32` vs `6-32` boards are the pre-arena test, registered as Gen 7. This report did not check
  that its bot is the launched `7s-32`.
- Twelve boards in each of the `5RZ32` and Gen 1 rows are against actors with other identities than the rest (the
  extra producer's).
- Live sources were read at their heads. All but one had stopped publishing new boards; a later run should give
  the same table unless the registry changes.
