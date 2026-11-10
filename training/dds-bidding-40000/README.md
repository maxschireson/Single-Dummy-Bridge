# Original 40K bidding-training deals and DDS tables

This is the exact solved-deal corpus used for the 40,000-pair / PPO-update-314
bidder inherited by Gen3, together with its separate 1,000-deal development set.
It contains full hands and DDS labels, not model weights or training auctions.

| Split | Deals | Compressed bytes | Chunks |
| --- | ---: | ---: | ---: |
| Training | 40,000 | 3,749,653 | 15 |
| Development | 1,000 | 94,381 | 1 |
| Total | 41,000 | 3,844,034 | 16 |

Every chunk is at most **262,144 bytes (256 KiB)**, below the requested 512 KB
transfer limit. `manifest.json` contains SHA-256 checksums and byte counts for
each chunk, each reassembled gzip, and each uncompressed JSONL file.

## Restore

After checking out branch `transfer/dds-bidding-40000-20261110`:

```bash
python training/dds-bidding-40000/restore.py --out /tmp/dds-bidding-40000
```

This uses only Python's standard library. It verifies all checksums, 52-card deck
partitions, 13 cards per hand, family IDs, original split membership, disjoint
families, indices, row counts and DDS table shapes before writing `train.jsonl`
and `dev.jsonl`. Repeating the command accepts identical files but will not
overwrite different files.

## Record schema

Each line is a JSON object:

| Field | Meaning |
| --- | --- |
| `index` | Original zero-based deal index within the split |
| `family` | SHA-256 of the canonical cyclic-seat-rotation deal representation |
| `hands` | Four exact PBN hand strings in **North, East, South, West** order |
| `dealer` | `N`, `E`, `S`, or `W` |
| `vulnerability` | `None`, `NS`, `EW`, or `Both` |
| `dds` | 5 × 4 integer declarer trick counts, from 0 through 13 |

Within each PBN hand, suits are dot-separated in **spades, hearts, diamonds,
clubs** order. Ranks are `AKQJT98765432`; an empty suit has no characters.

DDS **rows are S, H, D, C, NT**, and **columns are N, E, S, W declarers**.
Thus `record['dds'][4][2]` is South's double-dummy trick count in notrump.
These are perfect-information DDS results, not actual single-dummy play outcomes.

The source representation of unbid deals inserted a synthetic four-pass auction.
That placeholder is deliberately omitted: it was not the recorded training
auction. During PPO training, fresh auctions were generated on these deals.
This export is the hands and full DDS reward tables, not their stochastic auction
trajectories or optimizer state.

## Provenance and split rules

All **41,000** deals were regenerated using the original manifest's seeds and
indices. Every exact hand, dealer and vulnerability matched the recovered
dataset; every 20-entry DDS table matched the original saved SQLite cache.
**Zero new DDS solves** were performed. No family overlaps the train/dev sets.

The original generator is `bridge_harness.bidding_env.make_board`.
Canonical family hash buckets (`int(family[:8], 16) % 100`) are 0–79 for training
and 80–89 for development. The original checkpoint has `trained_pairs=40000`
and `step=314`. Original seeds, source-code hashes, BEN/solver hashes, source
manifest/state hashes and the recovered dataset checksum are in `manifest.json`.
The audit/export implementation is `scripts/export_dds_bidding_40000.py`.

Preserve these split assignments. The 1,000 development deals have already been
used for model selection; **they are not a fresh final test**. Models descended
from the 40K bidder have already trained on the training set.

The associated model and earlier review are documented at
`models/bidding/dds-40000/README.md` on this branch.
