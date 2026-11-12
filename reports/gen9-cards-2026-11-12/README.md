# Three real cards read into the card IR (G9-B6, 12 November 2026)

Procedure: `docs/gen9/card-intake.md`. Cards: `configs/cards/acbl-sayc.json`, `wbf-pryor-scerri.json`,
`wbf-laukkanen-nordgren.json`, each with a `provenance` block (source URL, confidence per field,
defaulted fields, agreements with no field). Check sheets here, made by `scripts/gen9_check_sheet.py`.

| Card | Source and format | Descriptor fields set | Carding fields | Agreements not placed |
| --- | --- | ---: | ---: | ---: |
| `acbl-sayc` | ACBL SAYC system booklet (prose); the ACBL card's text layer was unusable | 39 | 6 | 6 |
| `wbf-pryor-scerri` | WBF system card (England, 2025 European Online Senior Teams), PDF text layer | 23 | 4 | 11 |
| `wbf-laukkanen-nordgren` | WBF standard card (Finland, 2025 European Online Women's Teams), PDF text layer | 22 | 2 | 13 |

Read through a text extractor only: the three PDFs' suit symbols were partly lost, so fields that
depend on a symbol are marked low confidence or left out (for Pryor-Scerri the whole defence to 1NT
is uncovered). An intake agent that can render the page should read those fields from the image.
No card text is reproduced beyond the facts in the fields.

A fourth card tried, an ABF standard system card (Donovan-Heming, Queensland, 2025), could not be read
at all through its text layer (form fields not mapped to their labels); it would need the image.
