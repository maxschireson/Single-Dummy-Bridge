# Same-deal auction information with play under a different contract

This exploratory ownership-model experiment uses all 10,000 original games.
Each original deal's genuine BEN neural-only auction is added as a separate
information channel. The original played contract, declarer, dummy, actor,
visibility, play sequence, scores and ownership targets remain unchanged. It
does **not** claim that the auction and play form one legal bridge transcript.
Even the 31 passed-out auctions are permissible auxiliary information in this
synthetic task; they do not become actual played passout boards.

The rationale is that both signals depend on the same underlying cards. The
original play policy ignored auctions, so these examples describe auction-blind
play in a separately assigned contract. They can test ownership inference, but
cannot establish strength under genuine bidding-conditioned card play.

## Experiment

Use the same 22,676-parameter model as the matched608 pilot and seeds 731/732/733.
Both arms see the actual final **played** contract; the auction arm additionally
sees ordered real BEN calls. The no-auction arm receives zeroed auction tokens.
There is no suit permutation or hidden-hand input. The source card hash joins
auction and play; duplicate/missing groups, dealer/vulnerability differences,
impossible labels and split overlap are rejected. Original data are immutable.

The split remains 7,993 training / 1,008 validation / 999 test deals. Every
original position is used. Shards bound memory consumption. Both arms use the
same shuffled row order per seed, batch size 1,024, AdamW learning rate .001,
weight decay .001, dropout .15, maximum 40 epochs and patience 6. Validation
selection includes the unchanged capacity-balanced prior as epoch zero.

All six fits finish before test evaluation. The test split was used in earlier
work (including the matched608 pilot), so these are exploratory reused-test
results, not a fresh confirmatory benchmark. The matching-declarer/strain subset
is reported separately using the original played-contract features; its levels
can still differ from BEN's contract. Bootstrap intervals resample whole test
deals and average seed-level losses; this is not a prediction ensemble.

Run with the existing BEN TensorFlow environment:

```sh
python scripts/train_auxiliary_auction_play.py \
  --data ORIGINAL_COMPLETED_10000 \
  --auctions results/retrofit-10000/auctions \
  --matched results/retrofit-10000/reconciled \
  --out results/auxiliary-auction-play-10000
```

The output contains the frozen design/provenance manifest, per-epoch validation
metrics, best and last checkpoints for each run, per-deal test aggregates and
final results. Cache arrays are reproducible intermediates and need not be
archived. This experiment does not replay the 9,361 mismatched contracts or
deploy a model. BEN and DDS attribution/licensing remain as documented in
REAUCTION.md and the project credits; no external BEN source or pretrained
weights are redistributed.
