# boxctl: timeout=300
# boxctl: timeout=300
# loop session: azure5 plays round 2's two rungs (the net in the rollouts; the same with the value head in the seats) on
# the gate's deals 500-699 and returns to the collection by itself (unit loop-rungs, about 40 minutes).
set -euo pipefail
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
ls -la "$S/models/cardplay/stu-net-r2-20261113/policy.npz" | cut -c1-120; git -C "$S" log -1 --format='source %h'
for r in sp0 spr0; do echo "$r $(wc -l < "$W/runs/$r/results.jsonl") tables"; done
sudo systemctl stop loop-rungs 2>/dev/null || true; sudo systemctl reset-failed loop-rungs 2>/dev/null || true
sudo systemd-run --unit=loop-rungs --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$T/rungs.sh" jobs-azure5-r2.txt azure5
sleep 60; systemctl is-active loop-rungs loop-publish | tr '\n' ' '; echo; tail -n 2 "$W/runs.log" | cut -c1-140; tail -n 2 "$W/runs/l2b-p.log" 2>/dev/null | cut -c1-200; date -u +%FT%TZ
