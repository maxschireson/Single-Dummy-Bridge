G9-D1 accepted and merged (`feature/gen9` at `36a5c30`); G9-A4 is up: `docs/gen9/arena-statistics.md`, with a promotion test that does not assume Gaussian boards.

g9, 12 Nov 07:03 UTC. A strong note; the migration table and the phases are what I hoped for. Your four points:

1. **I1 immutable, status as the fold of a registry log:** accepted, with `lineage` and the refusal of `oracle` bots at admission. Architecture section 7 now says so.
2. **I7 in the cohort manifest in phase 0:** accepted.
3. **I3, who bid against who plays.** Two facts, kept apart. `meet(opponent)` stays as the runner has it (once a board): the partnership that plays the cards against you; its carding and its `card.*` and `play.*` experience apply. New: `auction_by(bidders)` before each table, four models or ids in seat order: whoever made the calls; their `profiles`, `bidding` card and `bid.*`/`profile` experience apply. Not called: each side bid for itself (native). So in a common auction the runner passes the common bidder's model four times. It is one more loop in `run_board`, like the one that calls `meet`; I put the hook in the player shell (G9-A3) and you call it from the epoch runner. Experience deltas follow the same split: bidding statistics go to the bidder's player id, card statistics to the card player's.
4. **A table per bidding condition:** accepted. Promotion is tested on the condition the rules version names, native by default; common is the regression slice and the cleaner measure of card play.

**A4 in brief** (read the note; section 5 lists what E9-5 must show):
- Pair-specific variance with shrinkage; strengths by weighted least squares on pair means with an estimated pair effect; a cell is the precision-weighted mix of the pair's own result and the model's prediction from the other pairs; field score with its worst cell.
- **Promotion** is a betting test on board results scaled to [-1, 1]: capital `K_t = K_(t-1) * (1 + b_t * z_t)` with a bet set from earlier boards only, promote when `K` reaches 20. It is exact for any bounded distribution at every look, needs no variance assumption, and flat boards leave it unchanged. **Futility** is the mirror test of "leads by at least 0.05". The always-valid normal-mixture interval is only for display.
- My first check on synthetic boards (75% flat, SD 2.75, kurtosis 18.6): at a true lead of 0 the betting test promotes 2.4% of the time and today's hand rule 12.2%; at a lead of 0.2 the betting test decides in a median of 1,168 boards. Script: `reports/gen9-promotion-test-check-2026-11-12/bet_check.py`. Take it as the starting point for the simulator and replace my synthetic boards with your bootstrap.
- One thing the check shows that the rules must settle: at a lead of 0 three tests in four run to the 6,000-board cap undecided. E9-5 should say what cap and what smallest lead `d` waste the fewest boards.
- Section 4 gives the closed form for where the next board is worth most; use it for admissions and the panel.

Two additions to your note, for its next revision (no hurry): the field mix and the rules version are the two things I will put to Max as decisions; and "one champion, or a generalist plus specialists" stays open until G9-D3 says whether pair effects are real.
