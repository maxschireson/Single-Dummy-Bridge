# Global dashboard tracking

The arena dashboard now separates cumulative training history from the selected
match cohort. `arena/global-stats.json` is the canonical compact summary;
`arena/global-tracking.js` refreshes it every 30 seconds. Ordinary score-feed
updates cannot replace this independent summary. Preserve the global section,
baseline JSON and script when rebuilding the Pages HTML.

Current verified sources:

| Statistic | Count | Coverage |
|---|---:|---|
| DDS bidder training boards | 40,000 | Exact for the deployed bidder; paired rooms count once |
| Single-dummy bidder training boards | 0 | Actual play targets are not yet wired into bidder fitting |
| Play training boards | 15,468+ | Confirmed latest-belief training families; full union with policy data pending |
| Policy audit lines | 27,329+ | Archived campaigns below; subsequent live exports pending |
| Latest bidding / belief / policy parameters | 1,524,776 / 308,726 / 39,512 | Deployed hashes recorded in JSON |

The verified migration archive contains 2,090 nonidentical audit continuations
from `g0001`, 20,482 from `g0001-bid40k`, and 4,757 from `g0001-direct`.
The latter two campaigns supply 3,700 boards and 25,239 alternative lines.
All 9,366 archived file hashes were checked against `FILE_SHA256.json`.
Zero-gain audits where both policies chose the same card, skipped audits,
ordinary match tables and PIMC hidden-layout samples are not alternative lines.
Recursive completed forks do count. No such totals are independent-board counts.

`ops/global_tracking.py` accepts cumulative training-family and receipt ledgers,
deduplicates families across model fits and receipts by immutable run identity
plus index, and refuses conflicting or regressing receipts. Partial backfills
remain lower bounds. Count training families only after a fit actually uses
them; collection is separate from training. DD and single-dummy supervision can
overlap and must not be blindly summed.

## Learning efficiency

For each generation record separate bidding-only and play-only matched gains
against its parent, measured at 32 samples with the other component fixed.
Divide the IMP gain per evaluation board by new training work in normalized
paired boards. One unit is two full table plays at 32 samples. A full paired
board at 16 / 32 / 64 samples contributes 0.5 / 1 / 2 units; a fork contributes
only its unreplayed fraction of 52 plies, times samples / 64. This nominal
budget normalization is not a measurement of actual DDS CPU cost. Keep actual
CPU time as another learning-efficiency axis. Repeated optimizer passes do not
create new training boards.

Bidding's DDS-table training needs a measured CPU conversion to a 32-sample
paired cardplay board; leave that denominator unset until calibrated. Report
gain confidence intervals with the same denominator. Pending values are not
zero, and current cross-component matches cannot supply isolated bidding gains.

## Live publisher integration

Publish updated complete `arena/global-stats.json` snapshots on
`research/direct-pairs-current` with a current timestamp. The existing arena
publisher lives in another environment; this change does not claim its private
training counters have already been connected. The source JSON and exporter
are ready for that integration and historical backfill.

## Decisions seen for each latest model

The model table reports parameter counts and `decisions_seen` together, tied to
the model SHA256. This counter covers training rows once in the **latest fit**,
not a claimed lifetime total through its inherited parent. Validation/test rows,
repeated optimizer epochs and newly collected but untrained play do not add rows.
Belief rows are labelled **observations**, since card ownership is a prediction
rather than an action decision.

| Deployed component | Parameters | Latest-fit training rows | Source |
|---|---:|---:|---|
| Bidding | 1,524,776 | Pending | Promotion confirms 40,000 boards and 314 PPO updates, not a trained-decision count |
| Public belief | 308,726 | 963,304 observations | `reports/belief_size_study_2026-11-09.md` |
| Auction-aware policy | 39,512 | 363,868 decisions | `reports/auction_policy_bootstrap_2026-11-09.md` |

A model ledger entry may include `decisions_seen` with `value`, `kind`
(`decisions` or `observations`), `scope: latest_fit`, `coverage` (`exact`,
`lower_bound` or `pending`), `detail`, and `source_url`. Pending uses null,
not zero. Populate this from the frozen training manifest when publishing a
checkpoint; preserve the identity and training scope. Do not carry counts from
a previous model to a new SHA256. The builder validates these optional fields.
