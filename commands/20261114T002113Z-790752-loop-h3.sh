# boxctl: timeout=300
# boxctl: timeout=300
# loop session: the nets alone head to head on azure5 (rungs.sh jobs-azure5-h3.txt in a unit of its own: the collection
# pauses, h3-n and h32-n play, the collection restarts on sps0).
set -euo pipefail
COMMIT=59fdfd752763197a4b7e7f9bac518d09bf94b1c0
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" -- bridge_harness scripts | tail -2
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
sudo systemctl reset-failed loop-rungs 2>/dev/null || true
sudo systemd-run --unit=loop-rungs --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$S/$T/rungs.sh" jobs-azure5-h3.txt azure5
sleep 20; systemctl is-active loop-rungs loop-collect | tr '\n' ' '; tail -n 2 "$W/runs.log" | cut -c1-200; date -u +%FT%TZ
