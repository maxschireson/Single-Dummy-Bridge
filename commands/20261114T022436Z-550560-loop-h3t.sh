# boxctl: timeout=1800
# boxctl: timeout=1800
# loop session: SiD (net) Stu R3 against SiD (net) v4.1 on azure6, rungs.sh jobs-azure6-h3t.txt in a unit of its own (the
# collection pauses for the head-to-head and restarts on the round 3 collection after it).
set -euo pipefail
COMMIT=19db74a4a9c985bc1b0e4ca08ffe207cc5653d71
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
for i in $(seq 1 40); do [ "$(systemctl is-active loop-rungs)" = active ] || break; sleep 30; done; sleep 40
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" -- bridge_harness scripts | tail -2
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
sudo systemctl reset-failed loop-rungs 2>/dev/null || true
sudo systemd-run --unit=loop-rungs --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$S/$T/rungs.sh" jobs-azure6-h3t.txt azure6
sleep 20; systemctl is-active loop-rungs loop-collect loop-rows | tr '\n' ' '; tail -n 2 "$W/runs.log" | cut -c1-200; date -u +%FT%TZ
