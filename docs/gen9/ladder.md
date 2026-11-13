# The ladder: strength by introduction date (G9-D9)

Gen 9 (dave; page part will). Read-only: it decides nothing. The ladder at the top of the arena page shows
every bot with boards on the registered feeds, placed by the date of its first board (x) and its strength
(y, with its 95% interval), labelled with its time per decision.

```
python scripts/arena_ladder.py collect --out rows.jsonl.gz          # every board of every registered feed
python scripts/arena_ladder.py fit --rows rows.jsonl.gz [--arrival CONTROL] --out arena/ladder.json
```

`arena/ladder.json` (schema `arena-ladder-v1`) is the page's input; `arena/ladder.js` draws it.

## Sources

The page's own: gh-pages `arena/gen6-sources.json` merged over the source list built into
`arena/reporting.js` (registry entries replace built-in ones with the same key), each read at its registered
revision (retired) or its branch head (live): `arena/data.json`, the replay index and its shards, and
`arena/manifest.json` for the bots' settings. Files are cached by commit (`~/.cache/arena-feeds`).

## Strength

ratings-v1 (`bridge_harness/arena_ratings.py`, docs/gen9/arena-statistics.md section 1) on the native
condition, each side bidding with its own bidder, so the whole bot; IMPs a board against the anchor, BEN (64),
fixed at 0: an outside bot that does not change between generations and has boards against every generation
from Gen 6 on. Counting is the page's (records after a feed's snapshot, the hidden BEN (32) and the accidental
cohorts out; allowed pairs; a deal family once per pair, earliest first; no self-play).

The fit is Bayesian. Each bot's prior is either

- **parent**: a match estimate of the bot against its parent from outside the registered feeds (box matches),
  so that no board counts twice: prior mean = the parent's strength + the estimate, SD = the estimate's
  standard error (a bench figure in tricks is converted at 3.8 IMPs a trick, E9-0, with 10% on the
  conversion added to the SD); or
- **weak**: SD 2 IMPs a board around the field mean, which is itself a free parameter (shrinkage toward the
  field).

Parents and priors are in `configs/ladder-bots.json`; today three bots have a parent prior (7s-32, 71s-32,
8s-32, all from the Gen 8 session's box matches as checked by p41 on `box/coordination`).

The **prior share** of a bot is 1 - (its variance with its own prior) / (its variance without it), the other
priors and the pair-effect variance held fixed: the part of its precision that its prior supplies. The page
draws a point hollow when the share is over one half.

## Variants

A bot whose published settings differ between feeds (file paths, names and identities ignored) is fitted
once per variant. A variant joins the bot's point when it differs from the main variant (most boards) by under
0.1 IMPs a board and by under two standard errors (g9's rule, 13 Nov 04:17 UTC); a variant whose feed publishes
no settings joins unless its boards differ by two standard errors, since nothing says its configuration
differs. A variant that does not join is its own point. The drill-down lists the variants of a point with
their share of boards, their difference from the main variant and what differs.

## Time per decision

From the records' `decision_timing` (the data behind the page's `decision-timing.js`; a feed whose records do
not all carry it contributes its feed-level total, as the page does): total wall-clock seconds over card
decisions with a choice (decisions minus forced decisions; forced moves' small time stays in the total).
Card play only, no bidding; host-dependent (Azure boxes, Codex and ChatGPT sandboxes differ; the split by
environment is in the file); not CPU time, which the records do not carry.

## Features

Each point's drill-down lists its settings against its parent's, grouped into named features (the names are
`FEATURES` in the script), each with the known impacts from `configs/ladder-feature-impacts.json`. An impact row
compares two configurations that differ only in that feature or says what else differs, and gives its source.
The drill-down also gives the ladder's own difference from the parent (`vs_parent`, covariance included).

## Candidates

Bots not in the arena (9a-32 from the arrival run) are optional points, marked `candidate`: a registered bot's
strength plus an outside match estimate, the two variances added.

## Limits

- The registered feeds were not designed as one experiment: bots meet different opponents on different deal
  sets, and a strength far from the anchor rests on chains of pairs. The pair-effect variance `t2` absorbs
  some of that; `Q` and `df` in the file say how well the pairs fit one scale.
- A parent prior is about a configuration close to the bot, not always the bot itself (`note` says what
  differs), and the box's own deals and hosts.
- Refresh: the file is rebuilt from current feeds by `collect` and `fit`; hourly for the first day.
