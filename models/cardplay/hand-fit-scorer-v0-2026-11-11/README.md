# Hand-fit scorer v0 (11 November 2026)

**Status: research prototype. Not the final package for the Gen 6 cutover.** Measured on the Gen5 bidder and the v5 belief net. No arena bot uses anything here, nothing under `bridge_harness/` or `scripts/` depends on it, and the nets must be retrained for any other bidder. Do not treat these files, weights or results as cutover inputs.

Prototype. 1,435,393 parameters. Outputs P(a hand would have made this seat's calls) from the hand type (suit lengths, honours A–T, high-card points), the seat, both vulnerabilities and the whole auction. A layout of the hidden hands is weighted by the product of the scores of each hidden seat's original 13 cards, so the play needs no bidder at the table.

Trained 22 minutes on two cores on 230,010 random deals bid by the Gen5 bidder (`analysis/auction_belief/gen_fit.py`, seed 2000; validation seed 9). Run `python restore.py` here to rebuild `hand_fit_v0.npz` from its parts (the repository ignores `*.npz`), then load it with `dict(np.load('hand_fit_v0.npz'))` and use it through `analysis/auction_belief/fit.py` (`log_score`) and `classes.py`. It was trained on auctions of the Gen5 bidder (`artifacts/v5/bidder.keras`, SHA-256 prefix 9ee52f3b) and must be retrained when the bidder changes.

Results: [reports/auction_belief_play_2026-11-11.md](../../../reports/auction_belief_play_2026-11-11.md). Not promoted; no arena bot uses it.
