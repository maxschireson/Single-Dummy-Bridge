# Full generated deal and auction cohort

All 24,000 original generated hand sets are supplied in boards/*.jsonl.gz.
Each record contains the full Board (hands, dealer, vulnerability, complete frozen auction, contract/declarer), canonical family, non-rotated deal ID, 80/20 family split and arena-selected flag. This includes passed-out deals and unplayed reserves. Gzip JSONL files can be streamed with the Python standard library.

manifest.json lists byte sizes, SHA256 hashes and counts. dd/*.jsonl.gz are incremental verified 20-value DD tables. Join by index AND family/deal_id; do not assume tables exist for every board until dd_complete=true. Axis order is strains S,H,D,C,N and declarers N,E,S,W. The final frozen auction DD duplicate NS score is supplied separately; passed-out deals score zero but still receive full DD tables.

Use exactly the supplied family split across play, auction belief and bidding training. Deduplicate against old imports by canonical family; auctions and play positions of a hand are not independent deals. This cohort is training data, not held-out v4 evidence. Full-hand/DD targets must never enter the acting bidder's public observation. Existing generation comparisons remain separate.

Download the transfer branch: git clone --single-branch --branch transfer/gen3-training-feed https://github.com/maxschireson/Single-Dummy-Bridge.git
Then read training/cohorts/cold-fresh-24000/manifest.json and the listed compressed shards. No custom restore tool is needed for this cohort. Refresh the branch to receive new DD shards.

DD computation is deliberately paused on this machine at the user’s request. No DD shards are included in this export. Compute the full 20-value DD tables in another environment using the pinned solver recorded in manifest.json (or document a rebuilt solver separately); preserve canonical IDs, axis order and family splits when returning results.
