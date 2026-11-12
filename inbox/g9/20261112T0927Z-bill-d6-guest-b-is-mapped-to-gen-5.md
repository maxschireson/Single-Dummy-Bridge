D6: guest-b is mapped to Gen 5 within 10-20 boards after a fix to the profile statistic (temperature 0.25); Gen 5 and dds40k are one system

bill, 12 Nov 09:27 UTC. Task G9-D6.

From bill, 12 Nov 09:27 UTC; copy to dave. feature/gen9-bidding-cards e626d73, reports/gen9-arrival-curve-2026-11-12.

Simulated with the shell's own arrive() and believed() (temper 1, floor 0.02) and my profile_evidence: a guest bidding Gen 5 against Gen 6, declaring rb-standard, 100 boards, 20 orders. Prior: card 0.70, flat 0.18, each held system about 0.04.

- With the old call models (eps 0.05, temperature 1) Gen 6 explains Gen 5's greedy calls nearly as well as Gen 5 does (0.09-0.14 nats a board), so the mapping is slow: gen5+dds40k 0.59 after 10 boards, 0.86 after 20, and gen6 still 0.12 at 20.
- held_systems now defaults to eps 0.02, temperature 0.25 (the house nets bid their argmax, so a sharpened softmax is the better likelihood for them): the gap becomes 0.46 nats a board, and gen5+dds40k are at 0.88 after 10 boards, 0.99 after 20; gen6 below 0.01 by 20.
- house-gen5 and house-dds40k cannot be told apart (0.003 nats a board; Gen 5 is a small fine-tune of dds-40000), so 'mapped to Gen 5' will show as gen5 and dds40k sharing about 0.99 (0.58 / 0.41 after 100 boards). For reading it makes no difference; for D6's report it should be stated, not read as a failure.
- The declared card scores worse than flat on this guest (−1.48 against −0.73 a board): rb-standard is broken on about 14% of its covered calls.

dave: if D7's pipeline calls held_systems() with its defaults, it gets the new call models from e626d73; if it passes eps explicitly, pass temperature=0.25 too.
