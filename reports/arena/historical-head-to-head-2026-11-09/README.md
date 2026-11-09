# Historical head-to-head results: 465 pre-migration pairs

Import this dataset once to add the earlier direct matches to the arena at
<https://maxschireson.github.io/Single-Dummy-Bridge/arena/>. It contains only
direct, swapped-partnership A/B/C matches from the final stopped cohort.

| Pair | Dashboard matchup | Paired boards | Net IMPs | Mean IMPs | 95% Student-t CI | W / T / L |
| --- | --- | ---: | ---: | ---: | --- | --- |
| AB | Gen 3.5 vs Gen 3 | 266 | -122 | -0.458647 | [-0.905708, -0.011585] | 38 / 174 / 54 |
| AC | Gen 3.5 vs Gen 2 | 132 | +22 | +0.166667 | [-0.419139, +0.752472] | 27 / 85 / 20 |
| BC | Gen 3 vs Gen 2 | 67 | -4 | -0.059701 | [-0.988887, +0.869484] | 15 / 35 / 17 |

Positive IMPs favor the first model. One paired board consists of two root
tables on the same deal and auction, with the partnerships swapped. The score
is `IMP(focal NS score - control NS score)`. Audit forks are excluded from
these statistics.

## Files

- `summary.json`: machine-readable groups using the dashboard's field names
  (`n`, `total`, `mean`, `variance`, `sd`, `se`, `ci`, `wins`, `ties`, `losses`),
  plus exact `sum_squares`, score histograms, model identities, and provenance.
- `pairs.jsonl`: 465 compact, index-ordered records with individual IMPs,
  root-table scores, canonical family hashes, timestamps, and episode hashes.
  This supports rolling windows, cumulative curves, and overlap checks without
  transferring full game trajectories.
- `source-manifest.json`: unchanged frozen source manifest.
- `validation.json`: checks performed against the archived original records.
- `export_historical_head_to_head.py`: reproducible exporter. It reads the
  original archive and uses its checksum-verified Python modules to replay
  and validate the episodes. It requires NumPy and SciPy.

## Dashboard integration

1. Fetch this directory from `research/direct-pairs-current`. Use immutable
   dataset ID `gen3-direct-pre-migration-2026-11-09-465` as the import guard.
2. Map A = Gen 3.5 (`auction-policy-v2`), B = Gen 3 (`public-belief-v2`), and
   C = Gen 2 (`combined-v2`). Verify model hashes, bidding and play settings
   against the receiving campaign. The exact cardplay models are in
   `models/cardplay/gen3-2026-11-09/`; all use the common 40k bidder.
3. Compare `family` hashes with new records before treating the observations
   as independent. Source records use manifest identity
   `8373b7b6adc88bb1cd3755840bb961797a61e47d9d8fbac79d1f81bf3cf8227f`
   and indices 0 through 464. New campaign indices may also begin at zero;
   `(source manifest identity, index)` identifies an imported record.
4. For each matchup, add `n`, `total`, `sum_squares`, `wins`, `ties`, and
   `losses`, then recompute the remaining fields:

   ```python
   mean = total / n
   variance = (sum_squares - total * total / n) / (n - 1)
   sd = variance ** 0.5
   se = (variance / n) ** 0.5
   ci = [mean - t.ppf(.975, n-1) * se, mean + t.ppf(.975, n-1) * se]
   ```

   Keep AB, AC, and BC separate. Do not average cohort means, variances, or
   interval endpoints. Reverse matrix cells negate the total/mean, reverse
   and negate the interval, and exchange wins/losses.
5. For selectable last-N windows and cumulative curves, concatenate the
   historical per-matchup index sequence before the new campaign's sequence,
   retaining source labels. Preserve a historical/current breakdown in the
   display and update the explanation of the combined evidence.
6. Add 465 to historical-inclusive head-to-head counts, not to the live
   collector's progress, throughput windows, training inventory, or target.
   Full historical trajectories have not been imported by this summary.

The dashboard snapshot inspected during export was `g0001-direct-cold`,
manifest `5169b9090c9b6bc3d95fbc6069d6ad76a817053c0903741e5ea84649891115e4`.
Its displayed model labels match this dataset. Its full scientific manifest
and individual deal families must be checked by the receiving collector.
This summary does not freeze or copy live dashboard totals.

## More frequent live updates

Max subsequently asked for more frequent dashboard updates because he enjoys
watching the results. The page already reloads every 30 seconds; the first two
`gh-pages` publications were at 09:08:20 and 09:18:36 UTC on 9 November 2026,
roughly ten minutes apart. Shorten the running publisher's actual publication
interval, with 60 seconds as the proposed target, and retain the existing
30-second browser refresh. Publish only when committed results change and
coalesce overlapping publication attempts. Keep publication asynchronous so
it does not stop collection. Preserve a visible snapshot timestamp.

The active publisher is in the receiving Codex environment, and its code or
configuration is not present on this source branch. This export records the
request; it has not changed the running publisher. The receiving task should
apply the interval there and verify two successive fresh publications.

## Scope and verification

The 3,235 older substitution-comparison pairs, other-bidder cohorts, and
partial checkpoints of these same direct records are excluded. Earlier
snapshots at 142, 318, 409, etc. are subsets, not additional evidence.

All 465 source episode and receipt checksums were verified. All 5,687 stored
tables, including audit branches, were replayed for validation; only the 930
root tables contribute to the 465 paired results. Frozen corpus, manifest,
models, DDS binary, root scoring, partnership assignments, and per-pair final
summary totals were checked. Each pair matches the archived final state.

Intervals are descriptive and unadjusted for repeated monitoring or multiple
matchups. The export does not make a promotion decision.

Reproduce with:

```sh
python export_historical_head_to_head.py \
  /path/to/Bridge_Gen3_Final_Migration_3700_2026-11-09.zip \
  --output /tmp/historical-head-to-head
```
