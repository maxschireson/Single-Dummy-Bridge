# boxctl: timeout=300
# boxctl: timeout=300
# loop session: azure6 plays round 2's longer-trained net alone on the gate's deals 500-999 (about 15 minutes) and returns
# to the collection by itself (unit loop-rungs). The checkout adds a bot and a job file; the collection chains are
# stopped by rungs.sh and restarted by it.
set -euo pipefail
COMMIT=a35dd0ebc69a47decb36e26c05ce4cd4332344a8
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
sudo systemctl stop loop-collect loop-collect-b || true
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
bash "$T/get_net.sh" 2s aca020142a5aec3017e69b0b6db04768440f5dbbb5ea688e0b8b55d96d0a8ca2
for r in sp0c spr0c; do echo "$r $(wc -l < "$W/runs/$r/results.jsonl") tables"; done
sudo systemctl stop loop-rungs 2>/dev/null || true; sudo systemctl reset-failed loop-rungs 2>/dev/null || true
sudo systemd-run --unit=loop-rungs --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$T/rungs.sh" jobs-azure6-r2s.txt azure6
sleep 40; systemctl is-active loop-rungs loop-publish loop-rows | tr '\n' ' '; echo; tail -n 2 "$W/runs.log" | cut -c1-140; tail -n 1 "$W/runs/l2b-ns.log" | cut -c1-150; date -u +%FT%TZ
