Reviews of G9-B4 and G9-B6: both accepted, with notes (unmeasured families, carding situation fields on the three cards)

sam, 12 Nov 07:59 UTC.

From sam, 12 Nov. Reviews of G9-B4 and G9-B6 (PR #26, `feature/gen9-bidding-cards` at `aae18f7`; I read `965a167`, its head). Both accepted. Notes below, none blocking.

**Tested.** `tests/test_gen9_cards.py`, `test_rule_bidder.py`, `test_bidding_systems.py` and every `tests/test_gen9_*.py` on your branch: 97 passed, 2 skipped (136 s).

**G9-B4 (match.py, factor.py hooks, E9-2).** Read in full. The code is correct as far as I can see: every rule table ends in the catch-all, so `card_distance`'s unguarded `next()` cannot fail, clause bounds use ±99 sentinels so `_signed_miss` never compares with None, and `boards_to_identify` counts correctly. Notes:
1. **Unmeasured families under a profile.** `residual` keeps only families with at least 20 covered calls and a break rate above 10%. A family under 20 calls (rare conventions, the kind where cards differ most) is therefore not in the residual, so `type_log_score(profile=p)` turns the filter off there even though nothing was measured. That contradicts the rule in your docstring: "believe the declaration where nothing says otherwise". I would put families with fewer than 20 covered calls into the residual (filter on), or store `measured` beside `residual` and treat unmeasured as residual.
2. **The catch-all family.** A break where the card's first fitting rule is the catch-all PASS means "the card is silent on this hand", not that the card was contradicted. It is counted as a break under family `catch`. It is not in any residual today, but I would report it apart from the rate.
3. **Skipped deals are not reported.** `card_distance` drops deals that raise ValueError or IndexError without a count. E9-2 found one `rule_bidder.py` crash. I would return `skipped` in the result, and send the crashing deal to g8, since the rule bidder is his file.

**G9-B6 (three real cards, check sheets, intake).** Notes in my area (carding fields are mine under I2):
1. **The cards' carding blocks declare directions and leads but no situations.** All three lack `signal_on_partner_lead`, `signal_on_declarer_lead`, `first_discard` and `trump_signal`. The signal reader then reads only their opening leads; a descriptor naming no signalling situation is inert for spots by design. The forms do state these: the ACBL card's "primary signal to partner's leads" and "to declarer's leads", and the WBF card's signal-priority grid. For SAYC the printed defaults are attitude on partner's lead, count on declarer's lead, standard discards. I will add the situation fields to the three cards from their sources on a branch of mine if you agree, or you can add them in intake step 2. Either way the intake doc should name the fields.
2. **Leads the lead table cannot express yet:** SAYC's "low from three small against suits, high against no-trump" and "second highest from four without an honour"; Pryor-Scerri's "second from a bad suit". These need two v1.1 lead fields (small-three lead by strain; four small: fourth or second). Leave them in `not_placed` until I add those fields.
3. Pryor-Scerri's "count low = odd" is standard count, which its block already says.
