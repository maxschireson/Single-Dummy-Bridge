# Card intake, first version (G9-B8), 13 November 2026

g9, while bill is away. Procedure: [docs/gen9/card-intake.md](../../docs/gen9/card-intake.md). Material: Max's two cards of one
partnership (names removed) and the style statements of its notes, on branch `team/gen9` under `samples/`.

## What there is

- `scripts/gen9_card_intake.py`: makes a reading bundle from a PDF or from photos of the pages. It does not fill the IR.
- `configs/cards/intake/sample-a-acbl.json` and `sample-a-wbf.json`: the two cards read into the IR, each with the notes' style
  statements. They sit outside `builtin_ids()`, so they do not join the library of profiles. Load them by path.
- Variants by seat and vulnerability in the loader (`Card.at`), applied by the compiler for the caller's seat and vulnerability
  (`CardSystem.for_context`).
- Two other blocks beside the descriptor:
  - `recorded`: agreements that `_fields.json` lists as not compiled (Drury, Smolen, Puppet Stayman), as structured values.
  - `style`: each style statement, with where it went or why it went nowhere.
- New fields:
  - `open.weak_top3`: honours among the top three for weak twos and three-level preempts.
  - `comp.balancing_nt_major`: the balancing 1NT range over a major.
  - `comp.vs_nt: woolsey`.
- Check sheets (`sample-a-*-check.md`), now with a table of hands on which each variant changes the opening.
- The four bundles, each with its run line in `runs.txt`:
  - `acbl-bundle.md` and `wbf-bundle.md` from the PDFs.
  - `acbl-photo-bundle.md` and `wbf-photo-bundle.md` from the photos.
  - The page images are not copied; the tool makes them again.

## Results

### The bundle tool

- **Layout.** Both PDFs and both photo sets were recognised as ACBL and WBF layouts.
- **Suit symbols.**
  - The ACBL text layer carries ♣♦♥♠ as characters.
  - The WBF text layer keeps them as Symbol-font private-use codes (U+F0A7 to U+F0AA). The tool decodes these, so 1♣ and 1♦ no
    longer read alike on this card.
  - The procedure says suit symbols are lost in WBF text layers. That holds for `pdftotext`. It does not hold for this card read
    with PyMuPDF. This is one card; others made another way may still lose them.
- **ACBL tick boxes.**
  - The flattened PDF draws them as small squares, filled when ticked. The tool found 173 boxes, 75 of them ticked.
  - Each box gets its label (the word to its left), the words before that, the header above it, and its colour (red for an
    alert, blue for an announcement).
  - I read about 50 of these boxes into the IR. All of them matched the page image.
- **Photos.**
  - OCR (tesseract) recovered 80.3% (ACBL) and 82.9% (WBF) of the words of three or more letters in the same card's PDF text
    layer. Mean word confidence was 72 to 82.
  - Neither suit symbols nor tick boxes are read from photos. The bundle says to read those from the image.
- **Form fields.** A fillable PDF's form fields (the ACBL editor keeps them) are read directly: name, type, value and nearby
  words.
  - Both sample PDFs are flattened and have none.
  - The reader is tested on a fillable PDF that the test builds. I have not run it on a public ACBL editor card: the sandbox
    cannot download one.
- **Section headings.** The tool groups text lines under the nearest heading above. This is a guess, and the bundle says so.

### Two cards read

| | ACBL | WBF |
| --- | ---: | ---: |
| Descriptor fields read | 35 | 36 |
| Carding fields | 13 | 13 |
| Variants | 4 | 4 |
| Recorded agreements | 21 | 14 |
| `not_placed` lines | 23 | 23 |
| Style statements: card / notes | 6 / 28 | 15 / 28 |
| `unsupported()` | none | none |
| Breaks against the card's own bidder, 1,000 deals | 0 of 4,273 covered calls | 0 of 4,268 |

**The notes' 28 statements:**

- 6 went to fields.
- 4 went to variants.
- 7 the defaults already state.
- 11 were not placed:
  - judgment ("bad", "flaws", "want the lead");
  - "respond light", which gives no number;
  - action over two- and three-level openings, and the doubler's rebids, which the compiler does not cover.

**The four variants (both cards):**

| Variant | When | What changes | Confidence |
| --- | --- | --- | --- |
| 0 | vulnerable | `open.min_hcp` 13 | low |
| 1 | vulnerable | `open.weak_top3` 2 | low |
| 2 | fourth seat | weak twos 8-10 | medium |
| 3 | first seat, favourable, IMPs | three-level openings on six cards, 0-10 HCP, any suit quality | medium |

- Variant 0 means that, with the rule of 20, only the 4-3-3-3 twelves pass.
- Variant 1 reads "sound vul" and "6-7 playing tricks" as two of the top three honours.

**Agreement between the two readings.**

- The two cards give the same compiled fields, with four exceptions:
  - The negative double limit: blank on the ACBL card, 5♦ on the WBF card.
  - 1m-3NT: 12+ to 15 on the ACBL card; the WBF card is silent, so the default 13-15 stands.
  - The carding signal on declarer's lead: on the WBF card only.
  - The Smith echo: on the ACBL card only.
- On 1,000 deals, 5 of 4,268 covered calls differ (0.12%). All five are negative doubles at the three level.
- I read both cards against the same notes. So this measures how consistent the two cards and one reader are. It does not
  measure accuracy against an independent reading.

**Calls for the owner to confirm.** These come from the lowest-confidence readings and are on the check sheets:

- Vulnerable, a 4-3-3-3 twelve passes, even ♠542 ♥A92 ♦A76 ♣A854 (variant 0).
- Vulnerable, weak twos need two of the top three, so ♠KJT964 ♥A5 ♦98 ♣T54 no longer opens 2♠ (variant 1).
- A 2-count with four hearts jumps to 3♥ over 1♥. The cards' mixed raise is read as the compiler's weak jump raise: four trumps,
  at most 9 HCP.
- 1NT-2NT is compiled as an invitation. On these cards 2NT is Puppet Stayman, and invitational hands go through 2♠.

## Code

- **`bridge_harness/cards/card.py`**
  - Variants: `at`, `variant_doc`.
  - The `recorded` block, checked against `_fields.json`.
  - The `style` block.
  - The new fields.
  - `identity_doc`: a bidder's identity leaves out fields added later while they hold their defaults. The 11 built-in cards keep
    their hashes; I compared before and after the change.
- **`bridge_harness/cards/system.py`**
  - `for_context`.
  - Woolsey.
  - The balancing 1NT over a major.
  - `weak_top3` in weak twos and three-level preempts.
- **`scripts/gen9_check_sheet.py`**: the variants table.
- **Tests.**
  - `tests/test_gen9_card_intake.py`: 12 tests, including five-card weak twos in third seat as a variant (the "can preempt 5
    card suits" case).
  - `tests/test_gen9_cards.py` still passes: 27 passed, 2 skipped.

## Found, not fixed

- **The derived 1NT rebid range.** For a 1NT range that starts at 14, the derived range is degenerate or empty. A 14-17 card
  derives (18, 17). `rb-precision`, with a 14-16 1NT, derives (17, 17).
  - The sample cards set `rebid.one_nt` themselves.
  - Fixing the derivation would change `rb-precision`'s compiled calls under the same identity, so I left it for bill.
  - **Fixed on 14 Nov (G9-B10, item 4).** A 1NT opening from 13 or 14 with two points or more below it now derives the
    balanced minimum under it: (11, 13) for `rb-precision`, (12, 13) for 14-17 with 12-point openings. The worry above
    was mistaken: `rb-precision`'s card does not cover rebids, so the derived range is never compiled into its calls;
    the rule bidder it describes rebids 1NT with balanced 11 to 13 (175 of 6,000 deals). No built-in card bids or reads
    differently (`tests/test_gen9_card_intake.py`).

## Against the task's done-when

- **Done:**
  - the agent procedure and template (the bundle and `template.json`);
  - two cards, each with provenance and a check sheet;
  - the style section compiled and tested on hands: "only preempt good suits vul" as `open.weak_top3` vulnerable, "can
    preempt 5 card suits" as a seat variant;
  - this list of what the cards held and the descriptor could not.
- **Not done:**
  - an older ACBL card (none in hand);
  - a card read from a photo as its own IR. The photos are renders of the same two PDFs: OCR recall is measured, and my
    reading used the images throughout;
  - the form reader on a public ACBL editor card.
- **Branch.** The work went straight to `feature/gen9`, not to a PR.

## Limits

- **Which seat a variant reads.** A variant applies to the caller's seat. Partner reads the base card. For example, responses to
  a fourth-seat weak two still assume 5-10.
  - A 1NT range by seat belongs in `open.nt`'s own entries, which both partners read.
- **Not compiled from these cards:**
  - four-card major openings in 3rd/4th seat (ticked on the ACBL card; "Can be 4 NV" on the WBF card);
  - seven-card four-level openings;
  - Puppet Stayman;
  - the 2♠ range ask;
  - mixed and 3♦ limit raises;
  - the defence to weak twos and preempts;
  - lead and signal exceptions.
  
  All of these are listed per card in `not_placed`, or kept in `recorded`.
- **Owner's confirmation.** The check sheets are not confirmed yet. Step 6 of the procedure is the owner's confirmation.
