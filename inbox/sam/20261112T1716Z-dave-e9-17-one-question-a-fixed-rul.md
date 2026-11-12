E9-17: one question — a fixed rule as a carding block with emission tables

dave, 12 Nov 17:16 UTC. Task E9-17.

From dave, 12 Nov 17:20 UTC. Task E9-17. One question; a yes is enough.

For E9-17 (g9: the reader told t-high's, t-low's and t-random's fixed rule), `r9t-32` is your `r9-32` pattern: `8x-32` plus `gen9.models`. Is this the right way to state a fixed rule as a carding block?

```json
"t-high": {"kind": "synthetic", "carding": {
  "descriptor": {"attitude": "standard", "count": "standard", "signal_on_partner_lead": "count",
                 "signal_on_declarer_lead": "count", "first_discard": "count", "trump_signal": "count"},
  "emission": {"partner_lead.count": [[0, 1, 0], [0, 1, 0]], "declarer_lead.count": [[0, 1, 0], [0, 1, 0]],
               "first_discard.count": [[0, 1, 0], [0, 1, 0]], "trump.count": [[0, 1, 0], [0, 1, 0]]},
  "phi": 0.2}}
```

The rows are P(low), P(high), P(middle) for each message, the same for both messages, so the count carries nothing and the card's place in its class is fixed. t-low uses [1, 0, 0], and t-random [1/3, 1/3, 1/3], which is even for classes of two and three cards. phi is 8x-32's factor for each type: 0.2, 0.5 and 0.25. There are no lead fields, so the opening lead is read as Gen 8 reads it.

If a different kind, or a missing situation, would leave spots unread that t-high's rule covers, tell me which.
