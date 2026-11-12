# System packages

**Work in progress. Not the final form.** One JSON file per bidding/carding system, read by
`bridge_harness/systems.py`. The schema, the ids and `_carding_fields.json` may still change,
and no arena bot, config or runtime reads this folder yet. Guide:
[docs/gen8_systems.md](../../docs/gen8_systems.md).

The entries describe bidders that exist today, each as its own system:

| File | What it is |
| --- | --- |
| `house-gen6.json` | Gen 6 bidder (graded alternatives) |
| `house-gen5.json` | Gen 5 bidder |
| `house-dds40k.json` | DDS-trained 40,000-pair bidder |
| `ben-gib-bbo-8742.json` | BEN's base bidder, neural calls without search. Draft: external weights, card not verified |

None of them has a convention card or declared carding. Add a system by adding a file; no
code names a system or counts them.
