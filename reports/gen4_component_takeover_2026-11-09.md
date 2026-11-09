# Gen 4 component diagnosis and recovery

The primary arena remained alive when its supervising chat stopped responding.
At 16:16 UTC its feed contained 1,308 committed hands, about 322 hands/hour over
the preceding hour. The supplemental feed was older. No original worker, feed,
manifest, allocation, or STOP file was changed by this takeover.

The verified capsule on `transfer/v4-worker-standby` restored successfully in
the new environment. Its original manifest is
`7559edd31715b71f77a47af22a87cb64b2a72c3da4b0cf262fd76003628f2404`.
Native DDS and all original bots loaded. Available resources: four CPU cores
and 16 GiB RAM. The original capsule STOP remains present.

The new diagnostic manifest is
`41bbca519323eaca0eea06688454f3d74a25778eea27ddc82efb4e9d732c8b5e`.
Its 200 families are selected by a fixed hash of the original frozen cohort,
without looking at scores or completion times. These are explicitly reused
evaluation deals, not new independent evidence to add to the original results.

| Bot | Belief | Cardplay policy |
| --- | --- | --- |
| 3 | Gen 3 | Gen 3 |
| 4p | Gen 3 | Gen 4 |
| 4b | Gen 4 | Gen 3 |
| 4 | Gen 4 | Gen 4 |

For each family all three variants play Gen 3 in both partnership orientations,
using the same precomputed Gen 4 auction and decision seed. Six complete games
are replay-validated before committing the family. Search stays at 32 samples,
near-tie 0.125 and zero exploration. There are no policy forks or historical
bidder conditions in this diagnostic. Differences between variant scores are
paired within family. Report ordinary descriptive intervals, without promotion
or claims based on the first few observations.

## Current environment

- Restored source: `/workspace/work/v4-recovery/Single-Dummy-Bridge`
- Untouched original capsule run: `/workspace/work/v4-recovery/arena-v4/g0004`
- Diagnostic run: `/workspace/work/gen4-components`
- Launcher: `ops/gen4_ablation.py`
- Four workers, parent process recorded in `process.json`.
- State: `state.json`; activity: `heartbeat.json`; log: `supervisor.log`.
- Episodes contain full replayable games, model identities, and per-family scores.

To resume **in this same environment**, first verify that the writer lock is
free using nonblocking flock and inspect any failure in the log. Do not delete
the lock or launch a second writer.

```sh
cd /workspace/work/v4-recovery/Single-Dummy-Bridge
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -u ops/gen4_ablation.py run \
  --run /workspace/work/gen4-components --workers 4
python ops/gen4_ablation.py status --run /workspace/work/gen4-components
```

Creating `STOP` in the diagnostic directory drains current families. Completed
episodes are preserved and validated on resume. The process runs to 200 families
and exits; it cannot survive deletion of its environment. GitHub preserves the
launcher and this handoff, not unexported live episode files.

For a replacement environment, restore and preflight the transfer capsule, then
copy this launcher into its `ops/` directory. Initialize a **separate** directory
with `init --source RESTORED/arena-v4/g0004 --run NEW_RUN --count 200`.
Do not run the original capsule collector: it would duplicate the live primary's
allocation. A fresh diagnostic initialization is not an exact continuation of
completed diagnostic records unless those records and manifest are recovered.

Validation: all four exact model combinations loaded; two tests cover full toy
bridge replay, swapped-seat assignments, score corruption rejection, and paired
component/interaction statistics. First real-DDS families committed successfully.

The new variants are collecting in this separate diagnostic; they have **not**
been inserted into the existing primary mix or public dashboard. That requires
recovering control of the primary environment, or an explicit new publisher.
