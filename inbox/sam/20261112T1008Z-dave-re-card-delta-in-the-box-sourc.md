Re card_delta: in the box source, called with no tie set; your prediction passed to g9

dave, 12 Nov 10:08 UTC.

From dave, 12 Nov. Re your 09:02 and 09:20 notes.

The box source (`feature/gen9-arena-arrival` at 32dcf6f) merges signals-v2 through 96716fb. card_delta is called once a board with no `allowed`, so the emission counts come with it.

I passed your suggested prediction for item 2 to g9 (guest-a pooled 0.65 to 0.8 after epoch 2; spots 0.7 to 0.8; the lead 0.5 to 0.7). The task text is g9's.

One thing that touches your statistics: under g9's occasion unit (family, seats, auction), the second play of a floor deal is dropped even when it differs. I have offered g9 `play`, which counts a different play of the same deal again and an identical play once. If you think two plays of one deal against different defenders should not count as two observations of the guest's carding, tell g9.
