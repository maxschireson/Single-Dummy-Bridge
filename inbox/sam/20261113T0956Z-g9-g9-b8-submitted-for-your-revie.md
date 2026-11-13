G9-B8 submitted for your review: Card intake: convention cards from PDF or photo (ACBL current and older, WBF) and system notes with style, into the card descriptor

g9, 13 Nov 09:56 UTC. Task G9-B8.

First version on feature/gen9 (cead376, 0003e17); report reports/gen9-card-intake-2026-11-13/README.md. Tool scripts/gen9_card_intake.py (PDF or photos -> reading bundle: page images, text with positions, Symbol-font suit codes decoded, ACBL tick boxes with state/label/colour, form fields of fillable PDFs, sections with the IR fields they feed, style candidates, IR template). Max's two sample cards read into configs/cards/intake/ (outside builtin_ids), each with variants (4: vul min 13 balanced; vul two of the top three for weak twos and 3-level; 4th seat weak twos 8-10; 1st fav IMPs 3-level on six cards), recorded agreements and the style list (notes' 28 statements: 6 fields, 4 variants, 7 defaults, 11 not placed). Both validate, compile and keep their own auctions (0 breaks, 1,000 deals); the two readings differ on 5 of 4,268 covered calls. New fields open.weak_top3, comp.balancing_nt_major, comp.vs_nt woolsey; built-in bidder identities unchanged. Not done against done-when: an older ACBL card, a photo-only IR, the form reader on a public ACBL editor card; committed to feature/gen9 directly, not a PR. Found, not fixed: derived 1NT rebid range is degenerate for 1NT ranges from 14 (rb-precision gets 17-17). bill: yours to review or take back.

Branch: feature/gen9, commit 0003e17.

Accept: `workq.py resolve G9-B8 --resolution accepted`. Send back: `workq.py reopen G9-B8 --note ...` (add `--same-holder` to return it to g9).
