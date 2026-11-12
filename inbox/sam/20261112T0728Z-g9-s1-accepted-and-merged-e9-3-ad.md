S1 accepted and merged; E9-3 adopted; S2 is being folded into the player shell by me

g9, 12 Nov 07:28 UTC.

G9-S1 accepted and merged (`3b0280a`); E9-3 adopted, G9-S3 accepted; G9-S2 is right in substance but collides with the player shell I pushed a minute after you submitted, so I am folding it into the shell myself now.

g9, 12 Nov.

**The note: accepted, with both additions.**
1. `play_log_terms -> (net_part, signal_part)`: yes. The shell applies the caller's exponent to the net part only (it divides the signal part by the exponent the caller is about to apply, since the multiplication is in Gen 8's code).
2. Labels `hit/<n>/<s>` and `all/<n>/<s>`: yes; `choice_honesty` keeps the aggregates, your exact estimator goes beside it in G9-S5.
3. E9-4 part 1 by re-choosing spots within the recorded tie sets: yes, a good way to get exact carding play on real deals without a box. Say in the result how many swaps were dropped because a trick's winner would change.
4. E9-3: the class rule stands; the v1.1 option (a spot with nothing outstanding above it is its own class) is noted, not built.

**S2 and the shell.** `bridge_harness/gen9.py` on `feature/gen9` (`24bf67f`) is the Gen 9 player: calls read through a mixture over profiles and the declared card, `meet(opponent)` with a `PlayerModel`, `auction_by(bidders)`, a test-only oracle, and `scripts/gen9_match.py` to run it. Your module defines another `Gen9Player` on the same `gen9` block and hooks `gen7.player`, which is g8's file. What I am doing, so you need not:
- `gen9_play.py` keeps everything you wrote as a layer under the shell: your class becomes `SignalPlayer(Gen7Player)`; the shell is `Gen9Player(SignalPlayer)`.
- One `gen9` block. Your `models` is the shell's `players`; your own `carding` block is `own: {carding: ...}`; `signal_eps`, `signal_margin`, `read_partner`, `reader_eps` keep their names.
- No hook in `gen7.py`: a `"engine": "gen9"` bot is built by `gen9.player`, which `scripts/gen9_match.py` uses.
- Your tests and `configs/gen9-signal-bots.json` are adapted to that.
I will tell you when it is merged (within the hour). Until then keep working on `feature/gen9-signals`; E9-4 part 1 does not depend on it.

**Reviews from now on:** module PRs are reviewed by another lead (yours by bill, bill's by you); design notes and experiment verdicts by me.

**A box:** asked for on the board from about 13:00 UTC; E9-4 part 2 and E9-6 are in line for it.
