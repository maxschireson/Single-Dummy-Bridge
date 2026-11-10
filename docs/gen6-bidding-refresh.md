# Gen 6 bidding refresh — 10 November 2026

Continue the promoted Gen5 `play50_anchor002` actor, SHA256
`9ee52f3baa79c837001e0cb515c61a9a179cb1bf66cd5503e46331245c014dcc`.
Keep the exact recipe: 2,048 duplicate pairs, 50% actual play / 50% DDS,
original-BEN KL weight 0.02, learning rate 2.5e-6, minibatch 64,
128 pairs per batch, two PPO passes, exploration 0.005. There is one candidate.
The original staged collector, cardplay, and updater are unchanged.

The frozen feed is `arena-gen5rz-ben-feed` at
`75f3219333abd3bb95e39135d7132f63561b6f54`. Its compact exports contain complete
auctions, hands, assigned actors, all played cards, and scores for 1,513 deals.
All 43 shard blobs and the manifest were checked against their Git blob hashes.
All 3,053 distinct root games were legally replayed and scored; 2,999 duplicate
common/native table references were removed. All 222 raw episodes already local
were SHA256-verified and their root trajectories matched the compact export.
The remaining full raw episodes were not downloaded: the compact complete-play
records provide every field required by this bidder's exact-auction recipe.
No counterfactual branches are introduced into the root outcome pool.

There are 1,182 new training families, 154 new development families and 177
new confirmation families. The complete pool contains 2,659 actual-play training
families, 40,000 DDS training families, 353 actual-play development families and
the existing 1,000 DDS development families. The prior 192-family final test is
retained as historical only and is not included in the fresh final comparison.
Canonical family splits are preserved. Explicit BEN, DDSD and belief confirmation
reservations were checked; no incoming overlap or bad-policy actors were found.
All 1,513 incoming families are distinct from the historical bidding pool.

The exact-auction table contains 3,440 auctions. Any freshly sampled auction
without an identical historical match is replayed by the same frozen Gen3
cardplay at 32 samples used in the Gen5 bidding recipe. Prior matching cached
plays are copied with checksums; live databases are never shared. Original BEN
weights provide anchoring; the original BEN training corpus is unavailable.

Run `scripts/prepare_gen6_bidding.py` to rebuild the dataset from the pinned
compact export and prior exact dataset. Reservation paths and resulting hashes
are recorded in `reports/gen6-bidding-refresh-data.json`.
Then run:

```sh
python scripts/run_gen6_bidding.py --plan configs/gen6-bidding-plan.json
```

The plan contains local paths and should be adjusted after restoration. The
runner verifies parent, anchor, data and source identities, takes an exclusive
lock, and resumes model/Adam checkpoints and pending sampled auctions. It runs
the pre-existing staged pipeline, development comparison and single-candidate
fresh confirmation. Report paired family IMP means, standard errors and 95%
intervals against the frozen promoted Gen5 parent. Training and validation do
not modify the active arena models.

Validation before launch: all full-play and provenance checks above; nine
existing bidding refresh tests passed; new scripts compile; `git diff --check`
passed. Training is running; no new strength claim or promotion has been made.
