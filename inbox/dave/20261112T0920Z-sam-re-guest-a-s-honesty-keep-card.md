Re guest-a's honesty: keep card_delta without the tie set; 0.65-0.77 is the effective honesty the reader should use (expected 0.72-0.78 on spots, the lead lower)

sam, 12 Nov 09:20 UTC.

From sam, 12 Nov. Keep calling it as you do, with no `allowed`. The lower value is the honesty the reader should use, not a bug.

- **Why not the tie set.** The house reader cannot see a guest's tie set when it reads a card: it assumes the whole class. So the experience must measure adherence against the whole class. That is the effective honesty: the bot's 0.8 diluted by the 8.5% of plays where its search ties only part of the class (E9-3). If `card_delta` used the tie set, it would estimate the nominal 0.8, and the reader would then assume more honesty than it sees. E9-4 part 1 shows over-assuming is the costly direction. A real guest has no tie set at all.
- **What to expect.** On relabelled boards (E9-4's learning curve) the estimate for 0.8 bots settled at 0.72 to 0.78 for spot signals, and reading at that value was at least as good as at 0.8. Your 0.73, 0.72 and 0.77 for the spot signals fit that. With 23 to 44 board-sides (about 100 to 180 occasions) each value carries about ±0.05.
- **The lead is lower by design.** For the opening lead the class is the whole suit, honours included, and the bot leads only among its tied cards. When the conventional card (say the king from KQx) is not tied, it leads uniformly among what is. So the lead's effective honesty sits lower (your 0.59).
- **Suggestion for the run's registered prediction (D6 item 2):** guest-a's pooled honesty estimate between 0.65 and 0.8 after epoch 2, spot signals 0.7 to 0.8, the lead 0.5 to 0.7; not 0.8 itself. guest-b: below 0.2 after one epoch still stands.
- **Also:** `card_delta` now writes the emission counts too (`7ef3cb8`). In the run they let the reader build an emission table per signal after 200 occasions. For guest-a's synthetic symmetric signals that changes little; for a BEN-like guest it matters (E9-7).
