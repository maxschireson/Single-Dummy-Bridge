# Gen 7 closeout results (12 November 2026)

**Question.** How did Gen 7, in its two versions (7.0 with policy net v4, 7.1 with v4.1), score against each
opponent over its arena run?

**Method.** `python scripts/generation_results.py --generation 7 --fetch gh --out results.json`, run 12 November
2026 at 19:20 UTC and again at 19:23 with the same counts. It reads the 60 Gen 7 sources in the dashboard registry
(`gh-pages:arena/gen6-sources.json` at `410b1af`), loads each score snapshot and replay index at its registered
revision (21 retired sources) or branch head (39), and applies the dashboard's rules: records after the snapshot
cutoff dropped; BEN (32) excluded; one observation per deal family and matchup, earliest completion kept. Common =
the Gen 6 bidder at all four seats; native = each side's bidder; bidding = native − common on the same boards. For
this run the script's actor order was brought up to the dashboard's (`71s-32` and the Gen 8 actors added in front),
which is what names and signs a pair, and it gained `--only` and `--skip` to pool a subset of the sources.

A first run at 18:04 UTC had 53 sources. The operator then registered the two sets drained at the switch to Gen 8
(`arena-gen7-1-mix2-azure1-feed` and six `arena-gen7-1-fresh3-azure3-ben64-*-feed` lanes), which this run counts.

**Result.** 22,021 counted boards from 22,700 observations. The table and its reading are on the
[Gen 7 page](../../docs/generations/gen7/README.md#results); per-source revisions and full statistics
(wins/ties/losses, standard errors) are in [results.json](results.json).

| Pair | Boards | Common auction, mean ± standard error | Won / tied / lost |
| --- | ---: | --- | --- |
| `71s-32` vs `7s-32` | 5,639 | −0.060 ± 0.035 | 566 / 4,535 / 538 |
| `71s-32` vs `6-32` | 2,234 | +0.302 ± 0.064 | 396 / 1,626 / 212 |
| `71s-32` vs BEN (64) | 4,721 | −0.003 ± 0.056 | 1,186 / 2,687 / 848 |
| `71s-32` vs BEN (16) | 378 | −0.159 ± 0.215 | 101 / 204 / 73 |
| `7s-32` vs `6-32`, every source | 3,083 | +0.262 ± 0.058 | 527 / 2,255 / 301 |
| `7s-32` vs `5RZ32` | 1,319 | +1.139 ± 0.114 | 470 / 703 / 146 |
| `7s-32` vs Gen 1 | 1,319 | +2.238 ± 0.125 | 666 / 534 / 119 |
| `7s-32` vs BEN (16) | 1,274 | +0.095 ± 0.119 | 357 / 700 / 217 |
| `7s-32` vs BEN (64) | 684 | +0.069 ± 0.153 | 177 / 386 / 121 |

**The pre-arena test apart.** The four `pre7` sources are registered as Gen 7 under the pair `7s-32~6-32`, but their
bot is not the launched one: identity `0264e01a9ec4` against `f0a578598673`, differing only in the tree's `trust`
(0.25 against 0.3; the operator's comparison of the two specs). Pooled on their own, each subset deduplicated within
itself:

| `7s-32` vs `6-32` | Sources | Boards | Common auction, mean ± standard error | Won / tied / lost | File |
| --- | ---: | ---: | --- | --- | --- |
| In the arena (`--skip` the four `pre7` keys) | 56 | 1,593 | +0.284 ± 0.081 | 281 / 1,155 / 157 | [results-without-pre-arena-test.json](results-without-pre-arena-test.json) |
| Pre-arena test, trust 0.25 (`--only` them) | 4 | 1,637 | +0.247 ± 0.077 | 265 / 1,215 / 157 | [results-pre-arena-test.json](results-pre-arena-test.json) |

The two subsets share 147 deal families, which the pooled row counts once (for the test, which played them first).

**Where each row's boards come from** (counted boards by group of feeds, in the run over every source):

| Pair | Groups |
| --- | --- |
| `71s-32` vs `7s-32` | 19bbdce5 1,459; independent 1,444; Codex 1,316; azure2 726; azure1 694 (first cohort 562, second 132) |
| `71s-32` vs `6-32` | independent 846; 19bbdce5 730; Codex 658 |
| `71s-32` vs BEN (64) | azure3 lanes 4,444 (first pool 2,928, second 1,417, third 99); independent 277 |
| `71s-32` vs BEN (16) | independent 378 |
| `7s-32` vs `6-32` | pre-arena test 1,637; Azure phase 1 870; Codex 343 (phase 1 188, self-play mix 155); independent 217; extra 13; azure2 self-play mix 3 |
| `7s-32` vs `5RZ32` | Azure phase 1 995; Codex 188; independent 101; cloud 23; extra 12 |
| `7s-32` vs Gen 1 | Azure phase 1 995; Codex 188; independent 102; cloud 22; extra 12 |
| `7s-32` vs BEN (16) | azure2 lanes 1,195; independent 79 |
| `7s-32` vs BEN (64) | azure3 lanes 606; independent 78 |
| `71s-32` self-play (818) | azure1 818 (first cohort 628, second 190) |
| `7s-32` self-play (552) | Codex 314; independent 230; azure2 8 |

**Limits.**

- Normal-approximation 95% intervals on the generation page, unadjusted for repeated monitoring. The 7.1 against
  7.0 pair was the subject of a stopping rule and was read many times.
- Pairs were collected at different times, mixes and deal sets, so comparisons across rows (7.0 against Gen 6 with
  7.1 against Gen 6, either against BEN) are not paired tests.
- Feeds absent from the registry are not counted. By design that leaves out the three Gen 7.1 sets closed on
  12 November at 06:32 to 06:39 UTC because policy net v4.1 was trained on their deals (393 boards).
- A board published is not always a board counted: of the 191 boards of 7.1 against 7.0 in azure1's second cohort,
  132 count, the other 59 being on deal families another collector had played for that pair earlier.
- Twelve boards in each of the `5RZ32` and Gen 1 rows are against actors with other identities than the rest (the
  extra producer's).
- Live sources were read at their heads. All but one had stopped publishing new boards; a later run should give
  the same table unless the registry changes.
