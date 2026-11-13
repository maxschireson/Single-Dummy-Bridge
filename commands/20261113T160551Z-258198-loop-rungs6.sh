# boxctl: timeout=300
# boxctl: timeout=300
# loop session: azure6 gets round 2's net and, when its two control rungs end (about 16:25), plays round 2's rungs
# (the net at the table too; the net alone and v2 alone on 500 deals) and returns to the collection (unit loop-rungs2).
# The checkout adds files and a job file; the running rungs' scripts are untouched.
set -euo pipefail
COMMIT=6fede601c00a19887fce259ec6995f9ba7ff7e4c
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" | tail -4
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
bash "$T/get_net.sh" 2 fa5df4e1a7f866a2fa3de4fcd195d3275c638c3b8d2a7b74585c5534b7395037
cat > "$W/rungs2.sh" <<'SH'
#!/bin/bash
W=$HOME/work/loop; T=$W/src/training/rollout-loop-20261113
while [ "$(systemctl is-active loop-rungs)" = active ] || [ "$(systemctl is-active loop-rungs)" = activating ]; do sleep 15; done
bash "$T/rungs.sh" jobs-azure6-r2.txt azure6
SH
sudo systemctl stop loop-rungs2 2>/dev/null || true; sudo systemctl reset-failed loop-rungs2 2>/dev/null || true
sudo systemd-run --unit=loop-rungs2 --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/rungs2.sh"
sleep 5; systemctl is-active loop-rungs loop-rungs2 loop-publish loop-rows | tr '\n' ' '; echo; tail -n 3 "$W/runs.log" | cut -c1-140
for r in l0b-pt l0b-pv; do echo "$r $(wc -l < "$W/runs/$r/results.jsonl" 2>/dev/null)"; done; date -u +%FT%TZ
