# boxctl: timeout=120
# loop session: the arena's rows for round 4, built ahead of the cut (round4_arena.sh on the records selected at 06:48;
# Nice 10, 4 workers, a unit of its own beside the experiment's last matches). The round's training reads r4arena/arena.npz.
set -euo pipefail
COMMIT=1a7116c902a116e40ff3034f969136a0cf67b4bf
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
git -C "$S" fetch -q --depth 12 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format="source %h"
ls "$W/r4arena/eps" | wc -l; ls "$W/r4arena/ben" | wc -l
sudo systemctl stop loop-arena 2>/dev/null || true; sudo systemctl reset-failed loop-arena 2>/dev/null || true
sudo systemd-run --unit=loop-arena --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --setenv=WORKERS=4 --property=Nice=10 -- bash "$S/$T/round4_arena.sh" "$W/r4arena" 45000
sleep 100; systemctl is-active loop-arena || true; tail -n 6 "$W/r4arena/arena.log" | cut -c1-200; date -u +%T
