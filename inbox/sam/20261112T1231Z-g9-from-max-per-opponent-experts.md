From Max: per-opponent experts that calibrate honesty per situation: E9-15 registered; order G9-X2 first reading, E9-15, E9-14

g9, 12 Nov 12:31 UTC.

From Max (12:29 UTC): per-opponent experts that calibrate honesty per situation. E9-15 is registered for you; order: G9-X2's first reading, then E9-15, then E9-14

g9, 12 Nov 12:33 UTC.

Max read the status with your BEN result in it and wrote: "We should read opponents' signals for known opponents, for example BEN's count signals, with a level of honesty calibration. Ideally we would have per-opponent experts that calibrate honesty per situation."

Your E9-7 is the first half of that. **E9-15** is the second (read the file; the design is fixed there before any held-out score):
- situations finer than the five keys: exact length where the table has parity, the number of equivalent spots, an honour in the suit, who led and from where, trump or side, dummy's long suit with no entry (where count is needed), and **the second round of a suit** (the completed high-low), which the reader ignores today;
- two models beyond your tables: a finer table with partial pooling (additive, so it lives in the experience store and every player gets one), and a small fitted expert per opponent;
- one output Max will want to look at as a bridge player: **BEN's honesty by situation**, a table of effective honesty with intervals, for each version;
- everything on your held-out split, in nats and in tricks through the bench, and against the number of tables of experience.

**Order for you:** the bench's first reading (G9-X2: the BEN emission model in tricks, which is also E9-10's prediction), then E9-15, then E9-14. E9-14's run that is already going can finish; report it when it does. E9-14 and E9-15 are the two halves of one thing, an expert per known opponent: its choices and its spots.

One number for your planning: a 240-board sandbox pilot of E9-0's strongest setting stands at +1.48 +- 0.41 IMPs a board after 85 boards (+1.85 nats a decision toward the true deal, honours weighted, at every decision). So information held through the whole play pays at about the bench's rate. A reader that helps on a fifth of the decisions should be worth about a fifth of that per nat, which is why E9-15 is reported per table and not per signalling occasion.
