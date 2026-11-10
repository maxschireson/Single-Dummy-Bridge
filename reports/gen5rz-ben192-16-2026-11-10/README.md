# Local 5RZ-192 versus BEN-16

A fixed 100-board paired cardplay match requested by Max on 10 November 2026.
Positive IMPs favor 5RZ. This compares the complete cardplay systems against
BEN; it does not isolate the effect of zero policy margin versus ordinary 5R.

## Frozen protocol

- 100 fresh canonical test-bucket families, seed `202611101745`; evaluation-only.
  None overlaps the preceding 256-board DDSD evaluation. Two auctions pass out;
  retain them as zero-score boards in the fixed cohort.
- Both rooms use the same auction from the promoted Gen5 candidate-2 neural
  bidder at all four seats. No bidding search or rescue. Thus this is a
  common-auction cardplay comparison, not a native-bidding comparison.
- Room 0: 5RZ North/South versus BEN East/West. Room 1 swaps the partnerships.
  Alternate the room execution order by board. Each board's result is the IMP
  conversion of room-0 NS score minus room-1 NS score.
- 5RZ has Gen5's promoted policy and belief, zero near-tie margin, zero
  exploration, and the unchanged Gen5R representative-layout algorithm.
  For positions with 10–13 remaining tricks it draws 768 worlds and solves at
  most 192 representatives with belief-moment weights. Other positions use
  ordinary 192-world sampling. Floating-point tie tolerance is at most 1e-9
  tricks; every selected move is checked against the recorded PIMC maximum.
- BEN uses the exact arena BEN-16 configuration and model hashes, source
  `9b5f43104aeac713a80b73513f2f2d6daf9f8769`. Opening-lead and play sample
  targets/minima are 16, DDS threads one, with native PIMC/ACE/SuitC disabled as
  in that profile. Its internal proposal filtering remains enabled.
- Two local workers, one BEN server per worker, numerical and DDS threads
  limited to one. Persistent cross-position DDS disk caching is disabled.
  Fixed sample budgets do not guarantee equal playing time; report both.
- Replay every complete table for legality and score correctness. Save each
  room atomically, then each complete paired board, so retries preserve already
  finished work. Fail on an invalid card, non-tie policy override, configuration
  drift, or engine error rather than substituting another player.
- Report mean IMP per paired board, its paired standard error, and a Student-t
  95% interval. Include wins/losses/ties and per-engine decision times. Interim
  scores are descriptive; the target remains 100 regardless of outcome.

## Source and reproducibility

Harness base: `552c13837e7f660464d0fba644c3d557bda59905`, the pushed 5RZ
implementation. The match adds `scripts/match_gen5rz_ben.py`; it does not alter
the arena mix or existing collectors. The 32-sample Z rule is applied unchanged
to the 192-sample representative configuration.

`manifest.json` pins model, runtime, BEN source/model, auction and DDS binary
hashes. `reserved-families.json` excludes these deals from training, and
`auctions.json` retains the complete frozen deals and bids.

Restore the promoted models using their checked-in restoration scripts, supply
the matching DDS binary and BEN runtime/dependencies, and run:

```bash
python scripts/match_gen5rz_ben.py run --run runs/gen5rz192-ben16-100 --workers 2
python scripts/match_gen5rz_ben.py summary --run runs/gen5rz192-ben16-100
```

Preparation freezes all 100 deals before play. The first two boards are an
end-to-end preflight and remain part of the fixed cohort. The existing tie-only
behavior test and four representative-sampling tests passed before play.

Status: the first two paired boards passed legal replay and all 80 nonforced
5RZ decisions selected a PIMC maximum (maximum gap zero). The remaining
98 boards are running locally. No completed-match result yet.
