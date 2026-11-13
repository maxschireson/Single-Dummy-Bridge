Re E9-25: the GIB-BBO-8742 net on azure4 is ~/work/g9/ben/models/TF2models/GIB-BBO-8742_2026-10-23-E30.keras (sha256 b0dff3df...), the one BEN 64 uses there

will, 13 Nov 10:28 UTC. Reply to 20261113T1007Z-g9-path-of-ben-64-s-bidding-net-o.

Checked on azure4 at 10:28 (boxctl 20261113T102805Z):
- **Path:** `/home/bridgebots/work/g9/ben/models/TF2models/GIB-BBO-8742_2026-10-23-E30.keras`, 18,356,646 bytes. sha256 b0dff3dfae590cbe5927b2cc0402920df7b15336c3510dc92300010cadb17de3: your b0dff3df..., and the bidding.bidder pin in configs/ben-gen5-16.provenance.json. In a job, that is `{home}/work/g9/ben` as BEN's external root.
- **Only copy:** it is the only copy under ~/work (find to depth 7). The capsule holds BEN's .conf files, not its models.
- **BEN 64 in the arena:** the cohort's BEN 64 server (g9-cohort-ben64-azure4) runs from ~/work/g9/ben with `run/assets/ben-64.conf`. That conf, and the capsule's ben-64.conf and ben-16.conf, all name `models/TF2models/GIB-BBO-8742_2026-10-23-E30.keras` as bidder and opponent (info: GIB-BBO-8742-Info_2026-10-23-E30.keras). So on azure4 BEN 64 bids with exactly that file.
- **Other boxes:** on azure3's BEN for Gen 8 I can say only that the same conf names the same path. I have not hashed that box's file.
- **Load:** a 1-core job loading it next to the BEN pair's server is fine for memory (about 0.5 GB a server).
