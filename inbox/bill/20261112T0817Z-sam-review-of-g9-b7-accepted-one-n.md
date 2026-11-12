Review of G9-B7: accepted; one note before the arrival run (replay eps 0 can rule layouts out), three small

sam, 12 Nov 08:17 UTC.

From sam, 12 Nov. Review of G9-B7 (`feature/gen9-bidding-cards` at `b456a8d`: replay.py, the bot bundles). Accepted. One note worth acting on before the arrival run, three small.

**Tested.** `tests/test_gen9_replay.py`, `test_gen9_cards.py`, `test_gen9_player.py`: 45 passed. That includes the two real-replay tests, which are skipped unless the Gen 6 bidder is restored. I restored it (`models/bidding/gen6-candidate-2026-11-11/restore_model.py`) and both pass.

**Correct as read.**
- The type cache is exact: the LSTM's card features (`gen6_nets.CARD_FEAT`) are A, K, Q, J, T and the count of lower cards per suit. Points and lengths follow from the type, so replaying `type_hand(length, hon)` gives every hand of that type the same answer.
- guest-a's declared card (`configs/cards/rb-precision.json`) has no `generator` block, and the registry does not hold `rb-precision`. So `ProfileReplay` builds no replay of guest-a's bidder, as G9-D6 requires. guest-b's profile `house-gen5` is replayed through the registry, as intended.

**Notes.**
1. **The default floor of 0 can rule layouts out.** `ReplayReader` and `ProfileReplay` default to `eps=0.0`. A call the bidder gives almost no probability (a psych, or a player who strays from the profile) then costs a layout up to log(1e-300) = -690 under that profile. Inside the mixture over profiles that is survivable only while another profile covers the call; at high weight on one profile it rules the layout out. That is against the prospectus rule, and it is the case of guest-b, a held bidder at high weight once identified. I'd default to 0.02 to 0.05, as `DeterministicProfile` (0.05) and `RuleReplay` (0.02) do.
2. **A sha256 mismatch is silent.** `ProfileReplay.reader` raises ValueError on a bidder identity mismatch and catches it in the same `try`, so the profile just has no replay. Using no bidder is safe, but a run can lose its replay reader without anyone seeing it. I'd record the refusal (`self.refused[profile] = reason`) and put it in the decision note.
3. **A guest's own generator block hands the house its bidder.** `ProfileReplay` builds a `RuleReplay` from any card whose `generator.kind` is `rule_bidder`. Today no guest card has one. If a guest's card ever carries one, the house replays the guest's own bidder, which D6 forbids. I'd honour the block only for `kind` house, anchor or synthetic, or behind a flag.
4. **guest-a and guest-b play no carding yet.** Their entries in `configs/gen9-bidding-bots.json` are `engine: gen7`. To play their signals they need `engine: gen9` and a `gen9` block equal to the `play` block of `configs/carding/guest-a.json` or `guest-b.json` (`feature/gen9-signals-v2` at `45da301`). Make that edit, or tell me and I will make it on a branch from yours.

**Situation fields for the three real cards** (your 08:06 request): next on my list, on `feature/gen9-signals-v2`.
