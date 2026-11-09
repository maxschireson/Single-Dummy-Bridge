# Gen 3.5 arena training feed

This branch contains **training-only supplements**, not a restored campaign or
complete base dataset. Collection continues in the original environment.

Restore the latest increment after checking out this branch:

    python training/restore_training.py --out /path/to/new-supplement

`training/latest.json` lists **all** immutable increments in order. The default
command restores the latest increment only; restore earlier increments with
`--snapshot training/snapshots/snapshot-0001`. Every increment is disjoint from
earlier increments in this feed, even when a straggling board finishes later.
An app receiving this feed for the first time must import every listed increment.
All binary chunks and the reassembled archive have SHA256 and byte-count checks.

The archive supplies `belief/` and `policy/` compressed NPZ tensors, their schema
and shard manifests, `sources.json` (canonical families, indices, splits, hashes),
and `provenance.json` (models and extraction rules). No logs, DDS caches, full
decision traces, model weights or optimizer states are shipped.

Merge the belief `shards` entries into the existing base belief dataset as source
`play`; retain previous BEN/bidding data and the selected parent model/Adam state.
Merge policy shards into the audited-IMP policy dataset. Copy shards under unique
increment paths and update their `file` paths; preserve hashes and all values.
Use canonical family IDs to reject duplicates against the old 3,700 and all other
training imports. Keep each supplied train/validation split and per-family weight.
The policy target `y` is the local audited chosen-minus-reference IMP contrast,
not the whole board outcome. BC boards have belief data but no A-policy labels.
Do not pool legacy/direct IMPs or report trained-on families as held-out v4 evidence.

The encoding, deterministic position selection, 128-belief-row family cap and
policy family weights match `scripts/prepare_mixed_training.py`. This feed is a
partial campaign snapshot and does not assert that the 21,300-board run finished.
Keep exporting-model hashes when training v4. A future v4 will require a distinct
manifest and evaluation cohort; do not overwrite the running Gen 3.5 weights.
