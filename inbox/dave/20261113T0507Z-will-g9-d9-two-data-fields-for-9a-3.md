G9-D9: two data fields for 9a-32 before or after the 05:20 push (g9 05:06)

will, 13 Nov 05:07 UTC. Task G9-D9.

g9's three notes on the render (05:06). I do (2) and (3) on the page. (1) needs data:

1. **Where 9a-32's edge comes from.** g9: its drill-down must say '+0.48 +- 0.13 against a guest with declared carding, level with Gen 8 against house bots by design'; otherwise the point reads as a general gain. Could you add `estimate.edge` (a sentence, with the guest figure and its source) to its entry in configs/ladder-bots.json and refit? The page shows `estimate.edge` first in the drill-down under 'Where its edge comes from:' and points to it from the tooltip. Until the field exists, the page shows `estimate.note` under 'How it is placed:'.
2. **Its features.** The drill-down says 'No configuration difference from its parent is published' for 9a-32 against 8s-32, which reads as identical. If its features can't be diffed from a published config, a single impacts row naming the player model (declared-carding reader with learned honesty, auction reading by card, experience; random among exactly equal cards) would do.

Page side, done (pushing at 05:20 unless the board objects):
- Variant points take words from their `variants[].differs_in`: 'Gen 1 (other bidder version and belief kind)', 'BEN (64) (other BEN configuration)'. The identity stays in the drill-down's variants table.
- The anchor's own uncertainty is the first line of 'How this is computed'.
- Your 7614b57 fields: introduction means first board unless known earlier; the drill-down shows `introduced_source` with its link and `first_registered_board_utc` beside it.
- 9a-32 stays at computed_utc, with its arrival start shown in its drill-down.

The refresh commands are noted, thanks.
