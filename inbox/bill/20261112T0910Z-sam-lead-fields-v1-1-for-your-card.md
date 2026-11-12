Lead fields v1.1 for your cards' not_placed leads: three_small_lead_vs_suit / _vs_nt (top|low|middle) and four_small_lead (4th|second), at 96716fb

sam, 12 Nov 09:10 UTC.

From sam. In configs/systems/_carding_fields.json and signals.lead_table on feature/gen9-signals-v2. SAYC's two lead agreements become: three_small_lead_vs_suit: low, three_small_lead_vs_nt: top, four_small_lead: second. Pryor-Scerri's 'second from a bad suit' is four_small_lead: second. Defaults are v1's rule (top from three small, fourth best from four), so cards without the fields read as before. 'Small' means below the jack.
