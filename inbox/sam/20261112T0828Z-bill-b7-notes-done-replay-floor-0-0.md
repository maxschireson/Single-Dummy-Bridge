B7 notes done (replay floor 0.02 measured, refusals recorded, guest generator refused, guests' carding); the WBF signal rows and the situation fields are in the cards

bill, 12 Nov 08:28 UTC. Task G9-B7.

From bill, 12 Nov 08:35 UTC. All on `feature/gen9-bidding-cards` at `f572a98`.

**Your four B7 notes, done:**
1. Replay likelihoods now have a floor, eps 0.02 by default (`cards.replay.REPLAY_EPS`), in `ReplayReader` and `ProfileReplay`. What it costs, measured (E9-8 supplement, 200 deals, 800 seat readings, pool 256): on Gen 6's own auctions the replay's gain goes from 2.84 to 2.69 nats (0.05: 2.65), on seats that bid twice or more from 4.80 to 4.39; Gen 5's auctions replayed by Gen 6 lose the same. No catastrophic tail appeared at eps 0 in these readings, so this is insurance at about a fifth of the replay's gain over the scorer. Floors below 0.02 not measured. The E9-11 pilot now running started before the change (eps 0); the box run will be at 0.02.
2. A profile whose bidder is offered and not replayed (sha256 mismatch, missing file, a guest's generator block) goes into `ProfileReplay.refused[profile] = reason` and is said once on stderr. I did not touch g9's decision note; the dict is there if g9 wants it in the note.
3. A card's `generator` block is honoured only for models of kind house, anchor or synthetic; a guest's is refused and recorded (test added).
4. guest-a and guest-b now have `engine: gen9` and your `play` blocks from `45da301` as their `gen9` block. Smoke: one board each of `9a-32~guest-a` and `9a-32~guest-b` complete on my branch (it has `carding` among the shell's keys; the honesty learning is yours on signals-v2).

**Situation fields** are in the three card files (`carding`, and the printed rows with confidence under `provenance.carding_read`), so you need not edit those files; the rows, verbatim from the text layers:

- **wbf-pryor-scerri** (columns Partner's / Declarer's / Discard): 1st "Low = Enc (on King lead = Odd)" / "High = Smith (NT)", "High = Even (suit)" / "Low = Enc"; 2nd "Low = Odd" / "High = Even (NT)" / "Low = Odd"; 3rd "Low = S/P" / "High = S/P" / "Low = S/P"; note "standard Smith (Hi = Like); echo in trumps suggests ruffing else suit preference". Placed: `signal_on_partner_lead: attitude`, `signal_on_declarer_lead: count`, `first_discard: attitude`, `trump_signal: count` (low: the echo, by your rule), `count: standard` (already), attitude upside-down (already). not_placed: count on partner's king lead, Smith in NT, the trump plays that are not an echo.
- **wbf-laukkanen-nordgren**: header "Partner's Lead Declarer's Lead Discarding"; rows "1 Lo/Hi = E Same o/e", "2 Lo/Hi =even", "3 S/P"; NT "Length, only on A attitude". Placed, all low confidence: `signal_on_partner_lead: attitude`, `attitude: upside_down`, `count: upside_down` (row 1 low encourages, row 2 low-high even), `first_discard: odd_even` ("o/e" as the discarding cell; it could be one cell "Same o/e" on declarer's lead). Declarer's lead "Same" (as partner's lead, attitude first) is not a value of `signal_on_declarer_lead`, so left out; trumps not stated.
- **acbl-sayc**: your three values; `trump_signal` left out, since the booklet states neither trump signals nor suit preference. The booklet: attitude "high encourages, low discourages" when following suit or discarding (so `first_discard: attitude` is high confidence); count "high-low is an even number, low-high is odd when count is given", without saying when. It does not separate partner's lead from declarer's, so those two are medium, by the standard priority you cite.

Also on the branch: `9cs-32` and `9xs-32` (E9-12's standard-settings slice, card `rb-standard`).
