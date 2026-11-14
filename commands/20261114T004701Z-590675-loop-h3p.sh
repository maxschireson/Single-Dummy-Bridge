# boxctl: timeout=300
# boxctl: timeout=300
# loop session (Max, 00:43 UTC): indicator 3 with power on azure6, rungs.sh jobs-azure6-h3p.txt in a unit of its own (the
# collection pauses for the head-to-head and restarts on the round 3 collection after it).
set -euo pipefail
COMMIT=545893b60c447bde818a20e0b56a133ad4da4a39
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" -- bridge_harness scripts | tail -2
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
sudo systemctl reset-failed loop-rungs 2>/dev/null || true
sudo systemd-run --unit=loop-rungs --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$S/$T/rungs.sh" jobs-azure6-h3p.txt azure6
sleep 20; systemctl is-active loop-rungs loop-collect loop-rows | tr '\n' ' '; tail -n 2 "$W/runs.log" | cut -c1-200; date -u +%FT%TZ
