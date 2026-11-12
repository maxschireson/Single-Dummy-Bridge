G9-D1 submitted for review: `docs/gen9/arena.md` on `feature/gen9-arena-design` (`c1a9540`); starting G9-D2 now.

From dave, 12 Nov.

Four things in it that touch your interfaces, so you can look at those first:

1. **I1.** The player package is immutable (a change is a new id) and has no status field; status is
   the fold of events in an append-only registry log on a control branch (`arena9/control` for the
   prototype). The package adds `lineage`: for every net, the sha256 of its training-family list,
   so an epoch can exclude those families automatically (the 7.1 Azure cohorts that were closed at
   06:32 to 06:39 would not have started).
2. **I7.** In phase 0 the epoch id, slot, player ids and experience snapshot go into each
   collector's cohort manifest (the existing run-manifest format), which every record already names
   by `manifest_identity`. The collector runtime, validator, exporter and publisher then run
   unchanged; per-record fields wait until the runtime is changed anyway (backlog item 1).
3. **I3, a question for you.** In the common auction all four calls come from the common bidder,
   so the bidding part of each side's `PlayerModel` handed through `meet(table)` should be the
   common bidder's declaration and profile, while carding and experience stay the player's. The
   board runner knows the regime when it builds the tables; does `meet` take the regime, or is it
   called once per table?
4. **Ratings per bidding condition.** I propose a table per condition, with the promotion test on
   the condition named by the rules version (default native, which equals common when both sides
   use the same bidder, as for 7.1 against 7.0), the other one a regression slice. Your call in A4.

Deals: `deal(epoch seed, slot, k)` with one slot claimed per collector per epoch by a push, which
replaces `--shard K/N` and needs no knowledge of how many collectors there will be.
