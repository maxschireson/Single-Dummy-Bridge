# Gen 4 candidate models: training data and process

These are training candidates, not arena promotions. The arena remains on its
existing models. A new deployed value network is deferred to Gen 5.

## Model locations

| Component | Candidate artifact after restoration | Parameters | Selected fit |
|---|---|---:|---|
| Belief | `models/cardplay/gen4-2026-11-09/belief.npz` | 308,726 | Pass 3; nine further passes did not improve selection loss |
| Card-play policy | `models/cardplay/gen4-2026-11-09/policy.npz` | 39,522 | Pass 3 of 8 |
| Bidding | `models/bidding/v4-actual-outcomes-2026-11-09/candidate.keras` | 1,524,776 | Actual-outcome fit; exact selection and comparison in its result file |

All binary parts are at most 512 KiB. Each package has SHA256 values for both
individual parts and reconstructed artifacts. Do not treat a model's save-file
hash as a behavioral identity across reserialization of the same weights.

```bash
python models/cardplay/gen4-2026-11-09/restore.py
python scripts/restore_actual_bidder.py models/bidding/v4-actual-outcomes-2026-11-09 --output restored-actual-bidding
```

## Belief

Continue the deployed large belief model and its Adam state. Training contains
126,608 distinct deal families, 1,630,369 information states, and 47,247,357
uncertain-card targets per pass. Of these families, 39,149 are recent. Historical
replay is retained; recent families receive twice the total family weight.
Extra positions and forks do not multiply a family's weight. Domain mass is
50% public play, 25% bidding-generated auctions, and 25% BEN auctions. Validation
uses 20,837 distinct families with the original source partitions preserved.
Learning rate is 0.0002 and batch size is 2,048.

The first three-pass fit selected pass 3. A continuation attempted nine more
passes, for twelve total, but kept its starting checkpoint. Thus the selected
model and selected optimizer are still from the original pass 3; the later
passes are not silently substituted into the package. Repeated presentations
are not additional independent observations.

Selected validation NLL is 0.864404 versus 0.865019 for the parent: a 0.071%
reduction, approximately 5.7 deal-family-clustered standard errors. Recent-play
ownership accuracy rises from 60.396% to 60.574%; older-play accuracy rises from
55.267% to 55.434%. Auction-only prediction worsens slightly. These are
descriptive results on selection validation, not a fresh final test or a playing
strength result. See `belief_v4_2026-11-09.md` and
`belief_v4_continuation_result_2026-11-09.json`.

## Card-play policy

Warm-start the auction-aware policy and add a distinct audited-IMP output,
retaining the historical prediction output as an auxiliary task. Fit on 25,239
audited action comparisons from 3,432 families. The union with the eligible
historical replay pool contains 21,510 distinct training families. Validate on
7,628 comparisons from 565 separate families. All historical and recent family
partitions remain separated.

The objective is recent family-weighted normalized IMP MSE, weight 2.0, plus
historical prediction replay, weight 0.25. AdamW uses learning rate 0.0002,
weight decay 0.0001, and gradient clipping. One historical minibatch accompanies
each audited minibatch; historical replay cycles deterministically. Eight
passes completed, selecting pass 3.

Validation IMP MSE changes from 2.459157589 to 2.459101836, a reduction of only
0.0023% (about 0.3 family-clustered standard errors). Historical auxiliary MSE
worsens from 0.8130483 to 0.8140115. 93.1% of training audits and 92.4% of
validation audits have zero IMP swing despite comparing different actions.
This establishes a completed fit, not a demonstrated policy improvement.
See `policy_v4_actual_imp_result_2026-11-09.json`.

## Bidding on actual hand outcomes

Start from the 40,000-deal fine-tuned BEN bidder and restore its Adam state.
This candidate does not start from the inconclusive cached-DD continuation.
Use 7,400 actual unbranched table results from 3,700 deals in the current
40,000-bidder epoch: 6,470 tables from `g0001-bid40k` and 930 from
`g0001-direct`. Exclude the 702 earlier-bidder tables and all card-play forks.
The incoming archive is hash-verified; contract, vulnerability, declarer,
tricks, score orientation, legal bids, and canonical deal-family identities are
checked before fitting.

Average the actual return across tables with the identical deal and auction.
This leaves 38,823 unique auction decisions: 30,873 from 2,939 training families
and 7,950 from 761 validation families. Each family receives equal total mass,
split equally between partnerships. All rotations of a deal remain together.
Inputs contain only the acting player's hand and the auction prefix known at
the time; results and future calls are labels only.

The outcome utility is signed IMP(actual NS score relative to zero)/10,
oriented to the acting partnership. This is an IMP-scaled score utility, **not**
an observed duplicate IMP difference or a causal estimate of a bid's value.
Actual play quality contributes noise to these labels. A small linear baseline
on frozen parent features is cross-fitted by family into five training folds;
validation baselines are fitted using training families only. This is training
machinery, not a new deployed neural value network. Positive advantages receive
larger regression weights, with exponential temperature 6 utility-IMP units and
weights capped between 0.25 and 4 before training-only normalization.

The method is a conservative adaptation of advantage-weighted regression
([Peng et al., 2019](https://arxiv.org/abs/1910.00177)); implementation is original.
The loss is twice the outcome-weighted bid cross-entropy, plus current-parent
KL with weight 0.5 and historical-parent KL with weight 1. Historical retention
uses 10,860 private auction-prefix observations from 512 separate replay deals,
excluding all current train/validation families. Historical targets are frozen
parent probabilities; no new double-dummy calculations are made.

Six passes use learning rate 0.000005 and minibatches of 256; BatchNorm moments
and dropout behavior remain frozen. A matched control starts from identical
weights and Adam state, uses identical sample order and retention losses, and
sets all outcome weights to one. Both are evaluated on the same family-mean,
outcome-weighted validation loss. The package contains the actual-outcome
candidate, not the control. The control's results are included to distinguish
reward weighting from merely imitating the logged bids more closely.

The archived bids were greedy. No softmax probability is passed off as an
observed sampling propensity, and no importance-sampling or off-policy IMP
strength claim is made. Lower validation loss does not establish better bidding
or performance on newly generated auctions. See the accompanying bidding
result report for the completed fit and paired comparison.

## Reproducibility and status

The bidding resume archive contains the selected model/Adam checkpoint, parent
architecture, exact outcome inputs and provenance manifest, partition, baseline
and targets, configuration, and both fit results. Its manifest names the
selected checkpoint prefix. The belief package preserves its selected optimizer
state separately. This upload does not modify any arena roster or collection
process. Integration and promotion remain pending Max's instruction.
