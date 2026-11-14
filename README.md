# Human-boards experiment, second part: every expert table (14 November 2026)

For `training/rollout-loop-20261113/exp_human.sh` (stages fit, all, big). Adult USBCs (Open, Senior, Mixed, Women's) of 2021
to 2023, every table of every deal (`usbc/human_episodes.py --all-tables`); the target is the card the expert played, bot
name `usbc`.

- `human_fit.npz`: the 3,841 tables whose every call the common bidder (6-32) gives at least 0.05 (113,489 rows).
- `human_unfit.npz`: the 18,428 tables with any other auction.

The 2025 USBCs and every junior event stay test data: none of their tables is here. Never merge this branch.
