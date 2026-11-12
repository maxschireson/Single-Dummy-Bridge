# The arrival run's rehearsal (G9-D6), one machine, 12 November 2026

A transfer branch: records only, never merged into source. Source: `feature/gen9-arena-arrival` (dave).

- `control/`: the control directory as the runner left it. It holds the registry log, epochs 1 to 4 (epoch 4 opened, not played), board rows and experience envelopes per epoch, ratings, experience snapshots, the rules file, and `distances/` (the arrival distances).
- `report.md`: the page (`scripts/arena9.py report`). `replay.json`: one epoch-3 floor board replayed from its manifest and snapshot, card for card.
- `run1.txt`, `run2.txt`: the runner's output. For a few minutes two runners played epoch 2 at once (my mistake; the runner now holds a lock), so 6 of epoch 2's boards were written twice with identical traces. Board rows are read first-written-first, and a repeated delta counts once in the experience store.
- Snapshots of epochs 2 to 4 were made before occasions named the opponent: the same deal against `9a-32` and against `8p-32` was counted once for the guest. The box run counts it twice.
