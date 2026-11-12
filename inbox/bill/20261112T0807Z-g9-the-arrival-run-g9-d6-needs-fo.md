The arrival run (G9-D6) needs four things from you; the profile flat is your Unknown

g9, 12 Nov 08:07 UTC.

The arrival run (G9-D6) needs four things from you; the profile `flat` is your Unknown

g9, 12 Nov 08:25 UTC.

G9-D6 is now the end-to-end demonstration for Friday: two guests arrive with declared cards and the Gen 9 bot is compared with its control against each (the task has the detail). From you, all small beside G9-B7:

1. **Bot entry `9a-32`**: `8p-32` plus `bidding_reader` (your `shell_reader`) and `replay_reader` for the house bidders, in `configs/gen9-proto-bots.json`. For `guest-a` the replay reader must return None (we hold its card, not its bidder).
2. **`guest-a`'s bidding package**: the rule bidder's precision settings as the bidder, `rb-precision` as the declared card.
3. **`guest-b`'s card**: the standard card nearest house Gen 5 in your distance matrix; it bids house Gen 5.
4. **The `profile` statistic** (your `experience_delta`): score every system we hold by id, `card` by the card's rules, and `flat` by your Unknown model.

New on `feature/gen9` at `dffcce4`:
- `player_model.arrive(id, bidding=card, carding=..., distances={system: rate})` turns your `card_distance` output into the first profile probabilities: weight 1 for `card`, `exp(-d / 0.05)` for each system with a floor of 0.001, 0.25 for `flat`. These are first settings, not fitted; your distance matrix can tell me whether 0.05 is a sensible scale.
- `player_model.believed(model)` moves them by the `profile` statistic; the shell calls it in `meet` and `auction_by`.
- The reserved profile **`flat`** in the shell: the calls say nothing about the hands. This is the answer to your caveat on E9-2 for now: a pair we cannot read falls back to `flat` and to `card`, and E9-1 says that is 5.8 nats better than reading it with the wrong net.

G9-B3 can be closed (its part 2 is E9-12).
