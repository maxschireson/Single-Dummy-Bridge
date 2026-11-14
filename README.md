# Human-boards experiment: training sets (14 November 2026)

For `training/rollout-loop-20261113/exp_human.sh` on the research branch (Max, 09:25 to 09:45 UTC: do the USBC's human
boards belong in training, and at what weight?). Built by `usbc/human_episodes.py`, `scripts/gen7_build_dataset.py
--policy-only` and `usbc/human_sets.py`.

- `human.npz`: 44,946 rows of 1,556 boards. Adult USBCs (Open, Senior, Mixed, Women's) of 2021 to 2023, one table a deal:
  the first, in a seeded random order, whose every call the common bidder (6-32) gives at least 0.05. The target is the
  card the expert played; bot name `usbc`. `human_tables.jsonl` lists the tables.
- `bot.npz`: 63,993 rows of 1,556 boards of the one-net SiD's self-play (`sp3t` blocks 600000 and 601000 of azure2), with
  the rollouts' values; bot name `stup0`.
- `mixed.npz`: both.
- `stu_eval.npz`, `stu_eval_usbc.npz`: 998 more boards of that self-play (`sp3t` block 602000), in none of the sets above, and
  the same rows with the bot named `usbc`.

The 2025 USBCs and every junior event stay test data: none of their tables is here. Compressed; the trainer wants them
rewritten uncompressed (exp_human.sh does it). Never merge this branch.
