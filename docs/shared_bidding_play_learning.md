# Shared bidding data and persistent DDS answers

The DDS-bidding campaign can train the auction-belief model without generating
another auction, DDS table, or played game. Cardplay can also persist each exact
DDS answer so subsequent runs only solve positions absent from the cache.

## Bidding records to auction beliefs

`scripts/prepare_bidding_belief.py` imports committed TRAIN batches from the
DDS-only bidding loop. Legacy auction records omit cards: the exporter checks
the pinned generator source, reconstructs deals from seed/attempt/offset, and
verifies every canonical deal ID and final contract. It never reads bidding
development or confirmation rows. Identical room auctions are deduplicated.
Each distinct auction supplies four complete-auction and four pre-call views.
Inputs are own hand, public prefix, dealer, vulnerability; hidden owners are
separate labels. Auctions beyond the existing 64-call capacity are counted and
skipped, never truncated.

A salted canonical-family hash assigns 80/10/10 belief train/validation/test.
Rooms, prefixes, rotations and vulnerability variants stay together. The
belief validation families were used to train the upstream bidder: they are
held out from belief gradients, **not** independent end-to-end bidding tests.
The exporter reserves all existing greedy-BEN corpus groups, including test
metadata, and optional exclusion lists. It exports no new test labels.

```bash
python scripts/prepare_bidding_belief.py \
  --bidding-run /path/to/dds-bidding-v1 \
  --legacy-data /path/to/auction-belief-50000-tensors \
  --exclude-groups /path/to/excluded-auction-deals-11200.json \
  --out runs/shared-belief/data
python scripts/train_bidding_belief.py \
  --data runs/shared-belief/data \
  --parent-weights /path/to/frozen/belief.npz \
  --out runs/shared-belief/fit --threads 1 --run-seconds 240
```

The fit warm-starts the existing 46,582-parameter network, mixes new examples
with 50% greedy-BEN replay, and reports the two validation distributions
separately. Selection uses mean complete-auction NLL, with a BEN regression
guard and the original checkpoint available as epoch zero. Test labels stay
unopened. A NumPy/TensorFlow agreement check verifies the exported weights.
The run checkpoints after epochs and resumes with identical arguments; it
does not update any bot manifest or claim playing-strength improvement.

For a larger later export, use a new output directory. Stable family splits
prevent previously reserved belief families from silently becoming training
examples. Keep bidder behavior provenance; the old source identifies batches
but does not record exact per-board league-opponent versions. Sampled learner
auctions and greedy deployed auctions are distinct distributions.

## Persistent exact cardplay solves

New `PIMCPlayer` instances, including `CombinedPlayer`, cache automatically at
`$XDG_CACHE_HOME/single-dummy-bridge/dds-positions.sqlite`, falling back to
`~/.cache`. Set `BRIDGE_DDS_CACHE=/shared/path/positions.sqlite` to choose a
shared location; an explicit empty value disables persistence for uncached
timing. Raw `DDS` calls can also set `cache_path` directly.

The exact key contains all remaining hands, trump, leader and ordered partial
trick. A solver-binary hash and output-schema namespace prevent incompatible
reuse. The payload stores the remaining trick count for **every legal card**,
not a policy-dependent average. Contract level, vulnerability, auction and
policy version do not change this exact solver question. No suit/rank/seat
canonicalization is attempted yet.

Before any hit is returned, validation checks the entire batch, including
counts, follow-suit, fixed hands and deck consistency. Hits are restored in
request order; duplicate uncached worlds are solved once; remaining misses
still use the related-layout batch interface. SQLite WAL permits separate
worker connections. Conflicting answers are rejected. Cache hits contribute
zero search nodes. Records distinguish requested worlds, native solves,
cache hits, and duplicate-world savings; old records remain readable.

The cache answers only the sampled position the bot actually requested. It
does not substitute the real hidden hand, force an updated belief model to
reuse old samples, or make training deals valid promotion tests. Cache held-out
evaluations as well. Changed policies can diverge into new positions, and
changed beliefs can produce different sampled layouts, reducing hits.

Use SQLite's online backup API (`PositionCache.backup`) when archiving a live
cache; copying just the main database can omit WAL transactions. Preserve that
snapshot with run checkpoints. Missing records can always be solved again.
Existing play logs contain aggregated estimates, so their old individual
solves cannot be recovered without rerunning the original sampling and search.

## Integration boundary

The running 8/16/32 and BEN comparisons use immutable source/weight manifests.
This checkout does not alter those running experiments. Enable caching by
adopting these source changes at a documented new-run/generation boundary;
freeze parent and candidate on that same source and retain their weight hashes.
Do not bypass source verification or silently rewrite an ongoing experiment.
Record cold and warm costs separately when comparing computation budgets.

The candidate belief weights must pass a paired play comparison before
promotion. Further bidding-record exports can be generated at the next bidding
checkpoint without forcing either collection loop to wait for the other.
