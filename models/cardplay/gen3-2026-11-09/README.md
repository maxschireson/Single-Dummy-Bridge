# Third-generation cardplay models

Four distinct trained cardplay models, exported unchanged from the frozen
`Bridge_Gen3_Resume_3701.zip` checkpoint. The six binary parts are each at most
524,288 bytes (512 KiB). No old deals, auctions, episodes, logs, or caches are
included.

## Restore

Check out `research/direct-pairs-current` in `maxschireson/Single-Dummy-Bridge`,
then run from the repository root:

```sh
python models/cardplay/gen3-2026-11-09/restore_models.py
```

Only Python's standard library is needed for restoration. The script verifies
every part, reconstructs the four `.npz` files in the adjacent `restored/`
directory, and checks the existing shared bidder. `manifest.json` records exact
sizes, SHA256 hashes, chunk order, and bot settings. No model is retrained or
converted during restoration.

| Model | Bytes | Parts | Used by |
| --- | ---: | ---: | --- |
| `public-belief.npz` | 1,142,040 | 3 | A and B |
| `auction-belief.npz` | 188,238 | 1 | C |
| `auction-policy.npz` | 126,893 | 1 | A |
| `prior-policy.npz` | 95,463 | 1 | B and C |

All three bots share the 6,153,107-byte bidder already committed at
[`models/bidding/dds-40000/bidder.keras`](../../bidding/dds-40000/bidder.keras).
The model manifest verifies its exact bytes; another upload is unnecessary.
Its BEN attribution and license remain in that directory.

## Bot configuration

| Label | Bot ID | Belief | Belief kind | Policy |
| --- | --- | --- | --- | --- |
| A | `auction-policy-v2` | `public-belief.npz` | `public` | `auction-policy.npz` |
| B | `public-belief-v2` | `public-belief.npz` | `public` | `prior-policy.npz` |
| C | `combined-v2` | `auction-belief.npz` | `auction` | `prior-policy.npz` |

Use 32 PIMC samples, `near_tie=0.125`, and `exploration=0.0`. The play-model
loaders and encodings are provided by this repository branch. The common bidder
uses BEN's feature encoding, `alert_supported=False`, and greedy neural-only
bidding with no DDS search or rescue.

## New deals and auctions

Max authorized generating new deals and auctions rather than transferring the
old corpus. Initialize a fresh campaign with a new manifest and run identity;
do not claim an exact continuation of the old board sequence. Freeze one common
auction per new deal and use the same deals and auctions for each paired
comparison. Preserve the existing deal-family training/validation exclusions.
Keep the old results and training records available separately for later use.

This directory supplies model weights, mappings, and verification. Running
cardplay also requires the repository's Python dependencies and DDS solver;
neither data collection nor training is launched by the restoration script.
