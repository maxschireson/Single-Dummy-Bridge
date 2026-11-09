# Additive Gen 4 training with an independent live arena

The arena continues collecting with frozen Gen 3/3.5 models. Training consumes
immutable exported data, then returns a candidate with parent hashes, data
snapshot, exclusions, recipe, metrics and model hash. Switch only at a fresh
block boundary after validation; never replace weights in an in-flight board.

Default: validate where the validation data already lives. The existing
`transfer/gen3-training-feed` branch now provides portable belief/policy tensors.
Use its 512-KiB chunk format and source family manifests for shared imports.
The migration archive supplies the earlier 3,700 boards; retain all older
auction/play training data as well. Neither a transfer nor a replay epoch adds
independent training experience.

First recipe to test, reflecting Max's directions:

* Keep historical belief and policy data. Give recent play families 2x weight
  in belief fitting; normalize within family so additional forks do not multiply
  its influence. Preserve the old BEN/DDS auction domains and belief Adam state.
* Make audited local IMP contrasts the main policy objective. Retain historical
  trick prediction as a smaller auxiliary objective. Normalize objective scales
  before weighting; record the coefficient and training-set scale estimates.
  Recency weighting is separate: recent audit families get 2x historical weight.
* Use the archived 3,700 as new training data and approximately 700 subsequent
  distinct families as validation for this first experiment. Partition by
  canonical family, including all rooms, rotations and forks. Preserve source
  splits in shared exports; experiment-specific remapping belongs in a separate
  immutable partition file, never in the original data. Check overlap with all
  parent and auxiliary training families.
* Compare 16/32/64 sampling as learning efficiency, with a common starting
  checkpoint and a common 32-sample strength evaluation. Track nominal sample
  work and actual CPU time. Shared multi-score solves help paired decisions but
  require careful cost accounting and divergent continuations still cost work.
* Bidding is currently DD-trained. Adding observed single-dummy outcomes is a
  separate trainer change, using a fixed play engine for bidder comparisons.
  Unplayed auctions do not have measured single-dummy counterfactual targets.

The optional `ops/training_exchange.py` transport can also capture completed raw
episodes and parent checkpoints without touching a running collector. Its
content-addressed chunks are incremental, verified and at most 512 KiB. The
already-established tensor feed is preferable when full raw records are not
needed. Neither transport automatically promotes a model or restarts an arena.
