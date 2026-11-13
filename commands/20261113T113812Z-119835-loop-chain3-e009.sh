# boxctl: timeout=600
# boxctl: timeout=600
# loop session: azure3's chain picks up the job file at e00923e (searched-lead rung l0-pl, pure Stu self-play sp0b).
# The run in hand resumes from its boards.
set -euo pipefail
COMMIT=e00923e4e538d7081d8e89fdf4d491fdf373f36a
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
tail -n 3 "$W/runs.log" | cut -c1-150
for r in l0-stu0 l0-p l1-stu1 l1-p l1-n l0-v1 l0-v1-p l0-n l0-v1-n; do [ -f "$W/runs/$r/results.jsonl" ] && echo "$r $(wc -l < "$W/runs/$r/results.jsonl")"; done
sudo systemctl stop loop-chain || true
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-110
grep -v '^#' "$T/jobs-azure3.txt" | grep -v '^$' | cut -c1-90
sudo systemctl reset-failed loop-chain 2>/dev/null || true
sudo systemd-run --unit=loop-chain --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure3.txt"
sleep 45; systemctl is-active loop-chain loop-publish | tr '\n' ' '; echo; tail -n 3 "$W/runs.log" | cut -c1-150; df -h "$W" | tail -1; date -u +%FT%TZ
