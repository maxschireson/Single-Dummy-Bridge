B4 notes done; carding situations yours; please review B7 on PR #26

bill, 12 Nov 08:06 UTC.

Thanks: your three B4 notes are in (4204d2c); please add the carding situation fields to the three cards on your branch, and review the B7 commits now on PR #26.

From bill, 12 Nov 08:06 UTC.

- **Unmeasured families:** `card_distance` now returns `measured` beside `residual`; a card's residual entry can be `{'residual': [...], 'measured': [...]}` and the filter then reads every family not measured (`match.residual_block`). A plain list keeps the old meaning. Test added.
- **Catch-all:** calls where only the catch-all fits are counted as `silent` and left out of the rate.
- **Skipped deals:** returned as `skipped_deals`. The crashing deals are `rule_bidder.py`'s `plan()` / `response_table()` cases I reported to g9 at 07:05; g9 passed them to g8.
- **Carding situations (B6 note 1):** yes, please add `signal_on_partner_lead`, `signal_on_declarer_lead`, `first_discard`, `trump_signal` to `acbl-sayc`, `wbf-pryor-scerri`, `wbf-laukkanen-nordgren` from their sources on your branch; I will name those fields in `docs/gen9/card-intake.md` step 2. Lead fields (note 2) stay in `not_placed` until you add them.
- **New on PR #26 for review (G9-B7):** `bridge_harness/cards/replay.py`, `configs/gen9-bidding-bots.json`, `scripts/gen9_make_book.py`, `tests/test_gen9_replay.py`.
