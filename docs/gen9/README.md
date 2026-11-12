# Gen 9 (design in progress)

> Work in progress on `feature/gen9`. Nothing here is adopted or deployed;
> [current system](../current-system.md) is unchanged.

Gen 9 develops what Gen 8 starts: a model of each player (declared card, matched profiles,
experience from finished boards) used to read their calls and signals, and an arena run as a
population that players join and leave.

| Page | What |
| --- | --- |
| [Architecture](architecture.md) | The overall flow and the interfaces between the areas |
| [Work plan](workplan.md) | Areas, tasks, checkpoints, team size |
| [Arena statistics](arena-statistics.md) | Rating table, field score, admission, the promotion test |
| Area design notes | `bidding.md`, `signals.md`, `arena.md`, `workflow.md`, added by the area leads at checkpoint 1 |

**Tests.** `python3 scripts/run_tests.py --prepare` builds DDS, installs what is missing, restores
the nets and runs every test file, reporting each skip and each test it could not run with the
reason (`--set gen9` for the Gen 9 set, `--with tensorflow,h5py` to cover the six tests that need
them). A fresh session sandbox runs everything in about 3.5 minutes:
[first run](../../reports/gen9-test-run-2026-11-12/README.md).

Live task and experiment state: branch `team/gen9` (`STATUS.md`). That branch is the team's
channel and is never merged into source.

**Base.** `feature/gen9` is `main` plus one snapshot commit of the Gen 8 prototype
(`feature/gen8-prototype-20261112` at `ca4fe53`), so Gen 9 work can use the Gen 8 system layer,
rule bidder, early play reading and match runner before Gen 8 is on main. The snapshot is
replaced by Gen 8's real source when that lands; Gen 9 code is kept in new files with small,
named hooks into Gen 8 files so the swap is mechanical.

## Code so far

| File | What |
| --- | --- |
| `bridge_harness/player_model.py`, `bridge_harness/experience.py` | Interfaces I3 and I6: what a bot is told about a partnership; experience as additive statistics |
| `bridge_harness/gen9.py` | The player shell: the Gen 8 prototype player with the mixture over profiles, hooks for the bidding and card-play readers, `meet` and `auction_by`, and a test-only oracle |
| `scripts/gen9_match.py` | `scripts/gen8_match.py` with Gen 9 bots allowed (same arguments) |
| `configs/gen9-proto-bots.json` | Prototype bots: `9p-32` (the shell with nothing declared; must equal `8p-32`) and the test-only oracle bots of experiment E9-0 |
| `tests/test_gen9_player_model.py`, `tests/test_gen9_player.py` | 26 tests; the second file needs the built solver (`python scripts/build_dds.py`) |

A bot with `"engine": "gen9"` runs only through `scripts/gen9_match.py`. The arena's collector
runtime does not know the engine, and oracle bots refuse to be built without
`BRIDGE_ALLOW_ORACLE=1`.
