# Card intake: reading a convention card into the card IR

> Gen 9 work in progress (G9-B6), by bill. Procedure for an intake agent; nothing here is adopted.

1. **Get the most structured source available**, in this order: the partnership's own system notes or
   a Word/Excel card template; the card as an image (render each page); the PDF's text layer last.
   PDF text layers of ACBL, WBF and ABF form cards lose the layout and the suit symbols (♣♦♥♠ are in a
   symbol font), so "1♣ 3+" and "1♦ 3+" read alike. Read symbol-bearing fields from the image.
2. **Fill `descriptor`** with flat keys from `configs/cards/_fields.json`, stating only what departs
   from the defaults, and `carding` with the fields of `configs/systems/_carding_fields.json`,
   including the signalling situations (`signal_on_partner_lead`, `signal_on_declarer_lead`,
   `first_discard`, `trump_signal`): without them the signal reader reads only the opening lead. Every number comes from the source. When the source gives points with
   distribution where a field is HCP, or leaves a range open, write the reading you used.
3. **Fill `provenance`**: source URL or file, format, reader and date; `confidence` per field (high:
   printed plainly; medium: needs a reading; low: a guess or a derivation, with the reason);
   `defaulted`: fields the card is silent on that the compiler needs; `not_placed`: every agreement
   with no field, in the card's own terms, so nothing is dropped silently.
4. **Restrict `cover`** to the context classes the card actually describes when a whole class could
   not be read (Pryor-Scerri: the defence to 1NT, whose suit symbols were lost, is left uncovered, so
   the filter defers to the scorer there instead of applying a guessed meaning).
5. **Validate**: `load_card(id).unsupported()` is empty, the card compiles, and
   `scripts/gen9_card_breaks.py` shows no breaks against the card's own bidder.
6. **Check sheet**: `python scripts/gen9_check_sheet.py <id>` (40 fixed hands: first-seat opening,
   responses to 1♥ and 1NT, action over a 1♦ opening, each with the rule that made it). A person or the
   card's owner confirms it; every disagreement becomes either a corrected field or a `not_placed` line.
7. **Field list**: an agreement that several cards need and that has a clear meaning over hand types
   is added to `_fields.json` and the compiler, with a test; until then it stays in `not_placed`.

## First version (G9-B8, 13 November 2026, g9)

- **Step 1, the bundle**: `python scripts/gen9_card_intake.py card.pdf --out DIR [--notes notes.md] [--id ID]`, or the photos of
  the pages in order (`p1.png p2.png`, with `--reference card.pdf` to measure OCR against a text layer). The bundle has the page
  images, the text with positions (suit symbols decoded where the text layer kept Symbol-font codes), the ACBL tick boxes with
  their state, label and colour, the text grouped under the layout's headings with the IR fields each section feeds, candidate
  style statements, and an IR template. The reader still reads every field against the images.
- **Three blocks beside the descriptor** (`bridge_harness/cards/card.py`):
  - `variants`: departures by seat (the caller's position from the dealer, 1..4), vulnerability (any | we | nv | fav | unfav |
    both | none) and scoring (any | imps | mp), each a set of flat descriptor keys; later entries win.
  - `recorded`: agreements whose `_fields.json` field is not compiled.
  - `style`: every style statement from the card and the notes, each with a `status` (field, variant, default, not_placed or
    recorded), where it went, and the reading used.
- **Step 6**: the check sheet adds a table of hands on which each variant changes the opening.
- **Placing style statements**: a statement becomes a field or a variant only with a number from the source, or with a reading
  written beside it and graded low. Judgment ("bad", "flaws", "want the lead") goes to `not_placed`.
- Results on Max's two sample cards: [reports/gen9-card-intake-2026-11-13](../../reports/gen9-card-intake-2026-11-13/README.md).
  The cards are in `configs/cards/intake/`, outside `builtin_ids()` and the profile library.

What three real cards needed (12 November 2026): a strong opening on 2♦ and a weak 2♣
(`open.strong_2c.call`, weak `2C`); six-card three-level preempts; a weak jump raise of a major;
a 1NT response range other than 6-10; a 3NT response to a major; a Jacoby minimum; a Michaels
minimum over a major; Multi-Landy over 1NT; limit raises on three cards; leaving four-level minor
openings undefined. Still without fields: Bergen raises, Drury, Puppet Stayman, Smolen, Lebensohl,
Kokish, Namyats, two-suited weak twos, responsive and support doubles, preempt discipline by
vulnerability, lead tables and signal priorities.
