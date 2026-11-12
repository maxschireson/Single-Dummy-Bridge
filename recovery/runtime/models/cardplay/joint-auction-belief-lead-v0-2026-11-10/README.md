# Joint auction belief net, opening leader, v0 (10 November 2026)

Prototype. 1,311,616 parameters. Trained 26 minutes on two cores on 2.2M random deals bid by the Gen5 bidder (`analysis/auction_belief/gen.py`, seeds 1000 and 1001). Run `python restore.py` here to rebuild `joint_lead_v0.npz` from its parts (the repository ignores `*.npz`), then load it with `dict(np.load('joint_lead_v0.npz'))` and use it through `analysis/auction_belief/joint.py`. It depends on the Gen5 bidder (`artifacts/v5/bidder.keras`, SHA-256 prefix 9ee52f3b) for its input state and must be retrained when the bidder changes.

Results: [reports/auction_belief_lead_2026-11-10.md](../../../reports/auction_belief_lead_2026-11-10.md). Not promoted; no arena bot uses it.
