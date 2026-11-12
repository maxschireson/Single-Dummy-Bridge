Carding situation fields: SAYC values below; please send me the two WBF cards' signal rows (their PDFs are not reachable from my session)

sam, 12 Nov 08:18 UTC.

From sam, 12 Nov. Carding situation fields for the three cards. The source PDFs are not reachable from my session (realbridge.online and the SAYC booklet copy are refused here), so I can do SAYC from a secondary source and need the two WBF cards' signal rows from you.

**acbl-sayc**: add to `carding`:
```json
"signal_on_partner_lead": "attitude", "signal_on_declarer_lead": "count", "first_discard": "attitude", "trump_signal": "none"
```
Provenance, confidence medium. The ACBL SAYC summary at zaremba.ch (based on the booklet) gives attitude signals and discards with standard count. Which signal applies where is the standard priority: attitude on partner's lead, count on declarer's lead, attitude on discards (e.g. Wikipedia, "Signal (bridge)"). Please confirm against the booklet text you read; if it names other situations, it wins.

**wbf-pryor-scerri and wbf-laukkanen-nordgren**: please paste me the rows of each card's signal section, i.e. the "signals in order of priority" grid (partner's lead / declarer's lead / discarding, vs suits and vs NT, first to third priority), plus anything about discards (Lavinthal, odd-even) or trump signals. I'll map them to the fields. Or map them yourself with these rules:
- First priority on partner's lead → `signal_on_partner_lead` (attitude | count | suit_preference). Declarer's lead → `signal_on_declarer_lead` (count | suit_preference | none). First discard → `first_discard` (attitude | lavinthal | odd_even | count). Following in trumps → `trump_signal` (none | suit_preference | count; a "trump echo" is `count`).
- Direction is `attitude` / `count` (standard | upside_down). "Low encourages" is upside-down attitude; "low = odd" is standard count.
- If a card differs between suits and no-trump, use the suit-contract row and put the no-trump row in `not_placed`. v1 has one field per situation; I'll add per-strain fields if a card needs them.
- If the card doesn't say, leave the field out rather than guess. A situation left out is read as Gen 8 reads it.
