# P04: standing collection and idle heartbeat

Owner: codex-stu-efficiency. [Loop assigned the coding slice](https://github.com/maxschireson/Single-Dummy-Bridge/pull/35#issuecomment-6883836024); loop deploys and handles exceptions. **Not deployed. No box allocation is claimed.**

When an ordinary `chain.sh` job file ends, an operator-installed standing recipe can supply fresh collection jobs. With no recipe the existing behavior remains. BEN chains do not enter fallback. A separate heartbeat records whether any `x8_match.py` process is present on the box; it reports an alert after more than 900 continuous observed idle seconds. The alert is diagnostic, not authority to restart anything.

## Integration

This PR is based on main. Copy `ops/stu_standing.py` into the active source via a reviewed commit, and apply [P04-chain-pub.patch](P04-chain-pub.patch) there. The two research scripts were checked against `research/rollout-loop-20261113` on 14 November and match the `5addd826af8b10d7343df51ada528a7327d059b6` snapshot. The patch does not import the research branch into main.

```sh
git apply --check /path/to/P04-chain-pub.patch
git apply /path/to/P04-chain-pub.patch
python -m unittest discover -s tests -p test_stu_standing.py
bash -n training/rollout-loop-20261113/chain.sh
bash -n training/rollout-loop-20261113/pub.sh
```

The helper uses Python's standard library on Linux. The patched scripts use the existing loop venv. Configure only one fallback-owning chain per box and allocate its workers alongside any other services. The lock prevents duplicate fallback owners; it does not allocate CPU against unrelated collectors. Pair, model/config source and precision remain operator choices; `run.sh` chooses bf16/recycling from its existing markers and run-name prefix.

## Operator recipe and range reservation

The default recipe path is `~/work/loop/standing.json`, overridable by `STU_STANDING_RECIPE`. This **example is not a deployed recipe**:

```json
{
  "box": 1,
  "pair": "stu4c-psta~stu4c-pstb",
  "seed": 9001,
  "workers": 2,
  "deals": 1000,
  "options": ["--episodes", "--one-room", "--common-only"],
  "name_prefix": "sp"
}
```

Loop must choose the actual standing pair, options, workers and prefix for each box, pin its source/models, and reserve this namespace before activation. **Proposed namespace:** seed 9001, first index `1,000,000,000 + (box - 1) * 10,000,000`, exclusive upper bound `first + 10,000,000`, box IDs 1–99. This makes all supported box bands mathematically disjoint. It does not prove that another experiment has never used this high range; loop must check/reserve it globally. No seed-131 or squeeze data is introduced. Only episodes, one-room, common-only and positive recycle arguments are accepted; options cannot override seed, output, deal count, bots or inputs.

Each job uses a fresh name such as `sp-fb1-1000000000`. A durable `standing-state.json` advances the index *before* launch, saves the exact recipe/hash, and records the result. A persistent lock covers the whole fallback loop. State belongs to one box; changing the box ID or exhausting its band fails rather than wrapping. An existing run directory is never resumed or overwritten.

## Stop, failures and resume

- Create `~/work/loop/FALLBACK_STOP`, or remove the recipe, to prevent another fallback job after the current one finishes. Neither interrupts an in-flight board. The marker affects fallback only, not the earlier explicit jobs.
- Successful completion advances to the next fresh job. Restarting the chain after success continues at the saved cursor. Changing the recipe between successful jobs affects only the next fresh identity.
- Nonzero exit, interrupted/reserved state, malformed state or an existing run identity stops fallback. Restarting the supervisor does **not** retry a failed or interrupted job. Loop must inspect and resolve the exception explicitly; the helper never clears a quarantine or deletes run artifacts.
- Preserve the state/lock directory with the run data. Do not delete or reset the cursor, copy another box's state, or reuse a run prefix to work around a failure. If state is lost, loop must reconstruct the highest reservation before resuming.
- The systemd unit must retain normal control-group termination so an interrupted supervisor does not leave an unowned child. The journal stays reserved on interruption, preventing an automatic second launch.

Disable adoption by omitting the recipe and retaining the old source checkout. Do not automatically kill or restart existing collectors to apply this change.

## Heartbeat

`pub/collection-heartbeat.json` contains process count, observation time, monotonic idle duration, boot ID and `idle_over_15m`. Process matching requires an argv token whose basename is exactly `x8_match.py`; an unreadable process table produces unknown state instead of a false idle assertion. Reboot resets the duration. Any matching process counts as active; this is **not** a stalled-worker or throughput detector.

`pub.sh` samples once per minute during its normal ten-minute publication wait and publishes early when the idle flag becomes true. First absence detection can lag up to one minute; publication/remote visibility also depends on Git push success. Active/unknown observations clear the idle interval. No automatic resource assignment or recovery follows the flag; loop handles intentional training/maintenance and failures.

## Validation and remaining deployment checks

Eleven sandbox tests pass: contiguous reservations and successful restart, box-band separation, nonzero exit without retry, crash-after-reservation refusal, stop marker, duplicate lock, seed/option validation, existing-run refusal, band exhaustion/box-change rejection, queued-job to fallback handoff/disabled default, and idle threshold/recovery/reboot/process matching. Fake runners write only temporary test files; no bridge game or live service was run. Shell syntax and patch application checks pass.

Loop still needs to reserve the high deal namespace, choose per-box recipes and worker budgets, and perform an isolated first-job/publisher check at deployment. P01/P03 and the P10 experiments are unaffected by this PR.
