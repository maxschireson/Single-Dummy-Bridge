# boxctl: timeout=600
# boxctl: timeout=600
# loop session: azure5's collection in two chains side by side: sp0 (the net's own lead) on six workers and spr0 (the
# lead rolled out) on two. Boards in hand are kept by the resume.
set -euo pipefail
COMMIT=b64ae5e7210f486cf6909e52526386d0c4f085a3
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
sudo systemctl stop loop-collect loop-collect-b 2>/dev/null || true
echo "spr0 $(wc -l < "$W/runs/spr0/results.jsonl") tables, sp0 $(wc -l < "$W/runs/sp0/results.jsonl")"
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-110
sudo systemctl reset-failed loop-collect loop-collect-b 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure5.txt"
sudo systemd-run --unit=loop-collect-b --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure5b.txt"
sleep 60; systemctl is-active loop-collect loop-collect-b loop-publish | tr '\n' ' '; echo; tail -n 3 "$W/runs.log" | cut -c1-150; uptime | sed 's/.*load/load/'; df -h "$W" | tail -1; date -u +%FT%TZ
