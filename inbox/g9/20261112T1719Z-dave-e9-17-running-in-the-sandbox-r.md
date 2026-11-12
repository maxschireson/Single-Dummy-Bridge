E9-17 running in the sandbox: r9t-32 on feature/gen9-e9-17; t-high's three matches by about 21:00 UTC

dave, 12 Nov 17:19 UTC. Task E9-17.

From dave, 12 Nov 17:35 UTC. Task E9-17.

E9-17 is pre-registered, leased and running in my sandbox.

- **`r9t-32`** is on `feature/gen9-e9-17` (8740a0d), which is sam's signals-v2 merged with feature/gen9; signals-v2 is where the emission tables live. It is `8x-32` plus the signal reader. Each stand-in has a carding block over the four spot situations, with emission tables that fix the card's place in its class: high, low, or even for t-random. The class term carries 8x-32's factor for each type (0.2, 0.5, 0.25).
- **Checked so far:**
  - `r9t-32` reads auctions exactly as `8x-32` does; the centred log weights are equal on two tables.
  - Four boards of `r9t-32~t-high` played at 16 CPU-s a board, about 400 boards an hour on 2 workers.
  - I have asked sam one question: is that the right way to state a fixed rule?
- **Order:**
  1. `8x-32` and `8p-32` against t-high, now; they do not depend on sam's answer.
  2. Then `r9t-32` against t-high, all on the same 400 deals (seed 917).
  3. Then t-low, and t-random if time allows.
- **Timing:** each match takes about an hour, so t-high's three matches should be done by about 21:00 UTC.
