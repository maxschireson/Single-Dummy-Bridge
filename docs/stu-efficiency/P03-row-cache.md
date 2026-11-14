# P03 per-record cache checkpoint

Draft implementation of the first part of loop's approved narrow P03 scope. Not deployed; no change to a trainer or collection recipe. Published row-block reuse and full R4c parity/family checks are still pending.

`scripts/stu_row_cache.py` runs the existing dataset builder once per episode, then reuses its compressed NPZ on subsequent runs. A cache entry depends on the original record bytes, builder/script/bridge Python source and native-library hashes, scorer hash, aliases, exact policy-only/rollout-gap flags, Python and NumPy versions. Entries are locked, written atomically and checked by output hash on reuse. A failed build does not publish an entry. Different records, code, aliases or scorer versions have separate cache keys. The manifest preserves sorted record order and multiplicity; it is not directly accepted by the current single-NPZ trainer.

Example (disposable sandbox paths):

```sh
python scripts/stu_row_cache.py --episodes /data/records \
  --builder /source/scripts/gen7_build_dataset.py \
  --scorer /source/models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz \
  --alias 'OLD=NEW' --cache /scratch/row-cache --manifest /scratch/row-manifest.json
```

Use the existing merge_sets.py on manifest entry paths in their recorded order for this initial checkpoint. Do not expand that into the deferred streaming trainer. No weighted resampling or family deduplication is introduced by the cache. Operators must first exclude held-out/test families from any training input; this helper does not infer split membership from filenames or authorize use of a record in training.

Validation: two real Gen8 self-play records (seed9001, indices1,000,000,000 and1,000,000,001) built separately and combined with the existing merge_sets.py produced the exact same arrays as the bulk builder: 83rows, two families. These are new sandbox acceptance fixtures, not R4c acceptance. Two unit tests cover warm reuse, record/version invalidation, corrupt output rebuilding and failed-build nonpublication. Builder source5addd826af8b10d7343df51ada528a7327d059b6. No speedup claim yet.

Remaining: use the pinned R4c input manifest to select published full/tail shards without overlap, recover payloads, normalize hashes by family/bot name, check held-out family exclusions across all sources, and prove exact R4c counts/row parity. Resolve any pre-existing overlap with loop. Add round integration only after that check. A corrupt metadata JSON currently fails closed for inspection rather than auto-repairing it. This draft is a durable checkpoint, not completion of P03.
