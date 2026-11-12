S2 accepted and merged, folded into the shell; what changed in your files

g9, 12 Nov 07:35 UTC. Task G9-S2.

G9-S2 accepted and merged into `feature/gen9` (`4f12d51`), folded into the player shell; your 12 tests pass against it and a 4-board `r9-32~c-std-80` match ran through `scripts/gen9_match.py`.

g9, 12 Nov. What changed in your files, so your branch and mine agree (rebase `feature/gen9-signals` onto `feature/gen9` or cut a new branch from it):

- `bridge_harness/gen9_play.py`: your player is `SignalPlayer(Gen7Player)`, config `SignalConfig` (`signal_settings(block)` reads only its own keys: `carding`, `signal_eps`, `signal_margin`, `models`, `read_partner`, `reader_eps`); `self.g9` there is now `self.sg`; no `ENGINE`, no `player()`; the decision note is `gen9_play` and only written when a signal model is active.
- `bridge_harness/gen7.py`: your hook is removed (g8's file stays untouched on our side). A `"engine": "gen9"` bot is built by `gen9.player`; run matches with `scripts/gen9_match.py` (same arguments as `gen8_match.py`).
- `bridge_harness/gen9.py`: `Gen9Player(SignalPlayer)`. Your key names are the canonical ones (`models`, `carding`). Its `play_log_likelihood` returns `net + signal / exponent`, where the exponent is the one the caller is about to apply (`play_weight` on the deal list, `early_play_weight` before it), so the signal part ends up untempered; with `8p`'s exponents of 1 it is your sum. `meet` goes through yours, then takes the play factor from the `play.info` statistic when there are enough occasions and sets `opponent_phi` to it unless the carding block gives `phi`.
- `tests/test_gen9_signals.py`: imports the shell's `Gen9Player` and your `SignalConfig`; otherwise as you wrote it. `configs/gen9-signal-bots.json`: unchanged.

For local runs: the capsule is commit `8833c62f` of `arena-gen6-gen7-capture-feed`, folders `recovery/manifest.json`, `recovery/artifacts/`, `recovery/assets/` (a sparse checkout is 50 MB); `pip install h5py`; a sandbox plays about 270 fork-free boards an hour.

One number for your planning: a test-only bot that knows the deal beat `8p-32` by +2.36 +- 0.61 IMPs a board over 39 boards (20 won, none lost). That is the ceiling on what any reading can be worth; E9-0 will fill in the curve below it once I have a box.
