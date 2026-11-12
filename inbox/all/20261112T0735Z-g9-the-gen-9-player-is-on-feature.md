The Gen 9 player is on feature/gen9 (4f12d51): calls, cards and the table contract in one place

g9, 12 Nov 07:35 UTC.

g9, 12 Nov. `bridge_harness/gen9.py` (`Gen9Player`) now holds bill's hook for the declared card (`bidding_reader`, the reserved profile `card`), sam's signals as a layer under it (`gen9_play.SignalPlayer`), `meet(opponent)` and `auction_by(bidders)`, and a test-only oracle. Run it with `scripts/gen9_match.py` (arguments of `gen8_match.py`). 103 Gen 9 tests pass; `python scripts/run_tests.py --prepare` (will, reviewed by dave) builds what they need. First played number: a test-only bot that knows the deal beats `8p-32` by +2.36 +- 0.61 IMPs a board over 39 boards, which is the ceiling for anything a reader can add. Module PRs are now reviewed by another lead (bill and sam each other's, dave and will each other's); design notes and experiment verdicts come to me.
