# Gen 7.1 settings matches on azure1 (12 November 2026)

Max, 13:52 UTC: "Can we explore the settings more deeply and see if we can restore even a small advantage from the better net?"
Fork-free duplicate matches with `scripts/gen8_match.py` (branch `feature/gen8-prototype-20261112` at `48982f7`; its Gen 8
engine additions are inert at their defaults), on fresh random deals (seed 7111, indices 0 to 2,999, the same deals in both
matches), common and native bidding by the capsule's 6-32 bidder. Bots in `bots.json`: `7s-32` and `71s-32` exactly as the
Gen 8 session's `7s-32` and `7s-32-v41` (Gen 7 standard with policy v4 and v4.1); `-w1` is the same bot with the layout-weight
exponent `play_weight` 1.0 instead of 0.5. Results are from the first-named bot's side.

- `m1`: `71s-32-w1` against `7s-32`. Does a retuned 7.1 beat 7.0 as deployed?
- `m3`: `71s-32-w1` against `7s-32-w1`. Is the better net worth anything at exponent 1.0?

Why exponent 1.0: the 4.1 session's reading bench (`reports/gen8-reading-by-net-2026-11-12` on `feature/gen8-p41-20261112`)
found every net does best at 1.0 (v4.1: +0.198 tricks a board against no reading, +0.158 at 0.5).
Operator: Claude session https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ.
