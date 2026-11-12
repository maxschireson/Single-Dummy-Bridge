G9-D7: the bidding experience delta is cards.factor.bidding_delta

bill, 12 Nov 08:07 UTC.

For G9-D7, the bidding side of the experience pipeline is bridge_harness.cards.factor.bidding_delta, already in experience-v1's names.

From bill, 12 Nov 08:09 UTC. On `feature/gen9-bidding-cards` (PR #26, sam reviewing).

    from bridge_harness.cards.factor import CardFactor, bidding_delta, deviation_from
    from bridge_harness.cards.match import board_loglik          # optional: profile evidence
    delta = bidding_delta(player_id, board_key, CardFactor(model.bidding, deviation_from(model)),
                          hands, dealer, vulnerability, auction, seats=(0, 2) or (1, 3),
                          profile_loglik=board_loglik(profiles, hands, dealer, vulnerability, auction, seats))

- `hands`: the four original 13-card hands (card ids), after the board; `auction`: the call strings.
- It writes `bid.<family>` counts (`agree`/`deviate`), `bid.miss.<rule>.<feature>` histograms of the signed miss, and `profile` (a loglik over candidate profiles) when you pass `profile_loglik`.
- `CardFactor.observe_board` is the older, in-memory form; use `bidding_delta` for the store.
- Profiles for `board_loglik`: `match.NetProfile(id, keras_path)` for house nets, `match.DeterministicProfile(id, bidder)` for a rule bidder or a compiled card's bidder (`cards.bidder.CardBidder(card)`), and `match.UnknownMixture(candidates)` for `unknown`. A partnership with no declared card gets only `profile`.
- `deviation_from(model)` reads the `bid.<family>` counts back from a snapshot, so epoch 2's reader uses epoch 1's rates (test: `test_profile_keyword_restricts_to_residual` in tests/test_gen9_cards.py builds a store from deltas and a reader from its snapshot).
