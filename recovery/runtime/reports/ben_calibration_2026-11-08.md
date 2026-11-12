# BEN card-play calibration — 8 November 2026

Status: collection started; no calibrated strength estimate yet. No model has
been trained. The 10,000-deal self-play collection and its training gate remain
separate and unchanged.

The predeclared experiment uses 200 independent held-out deals in four shards of
50 (deal seeds 20261201–20261204; decision seeds 23001–23004). Deal hashes are
reserved before any outcome is observed and must be excluded from all training.
BEN bids all four seats; each request receives only that bidder's hand and the
public auction. The resulting auction, contract and vulnerability are frozen for
two table games: PIMC NS/BEN EW and BEN NS/PIMC EW. Opening leads are chosen by
the players. Passed-out deals are reported separately from complete played games.

Our player: batch PIMC, 32 worlds for every non-forced decision, expected tricks,
uniform selection within 0.125 estimated tricks. No search budget is reduced.
BEN: commit `9b5f43104aeac713a80b73513f2f2d6daf9f8769`, portable neural/DDS path;
BBA, BGA PIMC, ACE and SuitC disabled. Bidding and play retain their configured
sample/search settings. Two DDS threads per BEN server bound CPU contention.
The saved configuration SHA256 is
`960d3b316967f22ed5c251a94b8e6714a249cc1851a02f193cc1f15e8f1dbfab`.

The initial attempt hit the 120-second HTTP deadline during bidding, before any
comparison game. The run uses a 600-second request timeout and an 1800-second
paired-board deadline. Completed auctions are retained across interruption;
partial auctions do not count as completed deals. Failed games must be retained
and reported, never replaced by a substitute player or silently excluded.

Final reporting must validate complete legal replay, exact settings, auction
transcripts, 200 unique original deals, and disjointness from training data. Report
tricks/board and IMPs/board with deal-cluster bootstrap intervals, elapsed time,
per-player decision time, and failures. Keep full records, configurations and
provenance in the durable experiment archive, outside Git.

This is an as-configured comparison, not an equal-time comparison. PIMC currently
ignores bidding evidence; BEN uses bidding evidence. BEN uses an IMP-oriented
configuration while PIMC optimizes expected tricks. These differences are part
of interpreting the baseline. A modest improvement will require a larger fresh
predeclared evaluation set; do not stop collection when a favorable result appears.

Validation of tooling: the full 31-test suite passed before adding auction
resume support. The new interruption/resume test checks that completed auctions
are retained and changed original deals rejected; all BEN adapter and paired
reporting tests passed after that addition. No playing-strength conclusion is
implied by these software checks.
