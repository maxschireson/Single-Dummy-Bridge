# boxctl: timeout=300
# boxctl: timeout=300
# loop session: azure6 plays two round-0 control rungs (v2 at the table; v2's value head in the seats) on the gate's
# deals 500-699 and returns to the collection by itself (unit loop-rungs, about 40 minutes).
set -euo pipefail
COMMIT=8e06911bda07f9bef11fa54322316bc523178392
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
sudo systemctl stop loop-collect loop-collect-b || true
for r in sp0c spr0c; do echo "$r $(wc -l < "$W/runs/$r/results.jsonl" 2>/dev/null) tables"; done
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
sudo systemctl stop loop-rungs 2>/dev/null || true; sudo systemctl reset-failed loop-rungs 2>/dev/null || true
sudo systemd-run --unit=loop-rungs --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$T/rungs.sh" jobs-azure6-r0c.txt azure6
sleep 50; systemctl is-active loop-rungs loop-publish loop-rows | tr '\n' ' '; echo; tail -n 2 "$W/runs.log" | cut -c1-140; tail -n 1 "$W/runs/l0b-pt.log" 2>/dev/null | cut -c1-160; date -u +%FT%TZ
