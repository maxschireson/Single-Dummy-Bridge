Heads-up: Gen 8's rule bidder r2 (after the snapshot) super-accepts transfers; 5 card tests fail on it

will, 12 Nov 07:33 UTC. Task G9-W6.

For when Gen 8 lands (G9-A5), no action needed today. I tried the base swap on a copy (G9-W6): feature/gen9 rebuilt on a stand-in main that has the Gen 8 prototype as it is now (`e9fde92`, "rule bidder r2 (structural fixes)"), not the snapshot (`ca4fe53`).

On that base `tests/test_gen9_cards.py` fails 5 of 18: `test_rule_bidder_auctions_never_break_their_card` for all five systems, at the same point. After 1NT-2H the r2 rule bidder bids 3S where the card's first fitting rule is 2S, "complete the transfer". Example: `('standard', ['PASS', '1N', 'PASS', '2H', 'PASS'], '3S', '2S', 'complete the transfer')`. On feature/gen9 as it is, all 18 pass. So r2 seems to add a transfer super-accept that the cards compiled from the settings do not describe.

Details: `reports/base-swap-trial-2026-11-12.md` on team/gen9. To reproduce: `python3 tools/base_swap.py --repo <checkout with feature/gen9, main and feature/gen8-prototype-20261112 fetched> --new-base <stand-in>` (the report says how I built the stand-in).
