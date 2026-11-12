# DDS-trained bidder: exact 40,000-pair checkpoint

`bidder.keras` is the actor-only deployment of PPO update 314, trained on
40,000 paired DDS-scored auctions. It has 1,524,776 parameters. See
[promotion.json](promotion.json) for source hashes, the separate 5,000-pair
review, and exact export checks. Deployment is greedy neural-only bidding,
without DDS search or rescue. All versions in the mixed play arena share it.

This is a fine-tune of BEN's `GIB-BBO-8742_2026-10-23-E30.keras`, not a model
trained from scratch. Credit belongs to the [BEN project](https://github.com/lorserker/ben),
its original model developers and contributors for the network, encodings and
initial weights. The upstream GPLv3 license is retained in
[BEN-LICENSE.txt](BEN-LICENSE.txt); this derived checkpoint is not represented
as newly Apache-licensed work. The project's new DDS/PPO training and actor
export are in `bridge_harness/bidding_ppo.py` and `ops/export_validated_bidder.py`.
OpenAI's Codex assisted Max Schireson with the implementation and experiments.

SHA256: `680470163f198802a5522d90f7ae4a1394fea3ca02ca4398f65c14eccb4934b3`.
Use the same feature encoding as BEN. Set `alert_supported=False`; the exported
model has one bidding-probability output and no training critic output.
