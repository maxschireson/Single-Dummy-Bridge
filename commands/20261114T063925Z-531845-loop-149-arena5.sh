# boxctl: timeout=300
# boxctl: timeout=300
# loop session (read-only toward the feeds; Nice 10, second checkout): the arena's records for round 4, selected ahead of the cut
# (round4_arena.sh with SKIP_BUILD=1: fetched, those in v2's set dropped, BEN at round 3's share against about 45,000 loop
# tables). In a unit of its own beside the style calibration; the log is ~/work/loop/r4arena/arena.log.
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q 7e815c6fc6648f10416060cbcfe40619a68bf11d
df -h --output=avail "$HOME" | tail -1
sudo systemctl reset-failed loop-arena 2>/dev/null || true
sudo systemd-run --unit=loop-arena --uid="$USER" --working-directory="$S2" --setenv=HOME="$HOME" --setenv=SKIP_BUILD=1 --property=Nice=10 -- bash "$S2/training/rollout-loop-20261113/round4_arena.sh" "$W/r4arena" 45000
sleep 60; systemctl is-active loop-arena || true; tail -n 5 "$W/r4arena/arena.log" 2>/dev/null | cut -c1-160; date -u +%FT%TZ
