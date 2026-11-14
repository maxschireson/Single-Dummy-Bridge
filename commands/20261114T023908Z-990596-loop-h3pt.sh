# boxctl: timeout=2400
# boxctl: timeout=2400
# loop session: the table net test (stu3-pst against stu0-ps) on azure2, rungs.sh jobs-azure2-h3pt.txt in a unit of its own (the
# collection pauses for the head-to-head and restarts on the round 3 collection after it).
set -euo pipefail
COMMIT=28b5b06c236da5d7d54e9c34a6b9d40ad7985e06
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
for i in $(seq 1 60); do [ "$(systemctl is-active loop-rungs)" = active ] || break; sleep 30; done
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" -- bridge_harness scripts | tail -2
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
sudo systemctl reset-failed loop-rungs 2>/dev/null || true
sudo systemd-run --unit=loop-rungs --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$S/$T/rungs.sh" jobs-azure2-h3pt.txt azure2
sleep 20; systemctl is-active loop-rungs loop-collect loop-rows | tr '\n' ' '; tail -n 2 "$W/runs.log" | cut -c1-200; date -u +%FT%TZ
