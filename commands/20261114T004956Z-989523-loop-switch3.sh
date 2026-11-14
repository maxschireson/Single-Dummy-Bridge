# boxctl: timeout=7200
# boxctl: timeout=7200
# loop session: azure3's collection to round 3's net in the rollouts, once its BEN session (loop-bensession) has ended and
# restarted the old chain: sps0b stops, the chain restarts on 57ce557 with sp3sb (stu3-psa~stu3-psb), the row publisher
# moves to sp3sb. As on azure1, 2, 5 and 6 at 00:43-00:46 UTC.
set -euo pipefail
COMMIT=57ce557
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
for i in $(seq 1 85); do [ "$(systemctl is-active loop-bensession)" = active ] || break; sleep 60; done
systemctl is-active loop-bensession || true
sleep 30
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
sudo systemctl stop loop-chain loop-collect-b loop-rows 2>/dev/null || true
echo "$(date -u +%FT%TZ) sps0b stopped: the collection moves to sp3sb (round 3's net in the rollouts)" >> "$W/runs.log"
sudo systemctl reset-failed loop-chain loop-collect-b loop-rows 2>/dev/null || true
sudo systemd-run --unit=loop-chain --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure3.txt"
sudo systemd-run --unit=loop-rows --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$T/rows.sh" sp3sb
sleep 30; echo "azure3: $(systemctl is-active loop-chain loop-rows loop-publish | tr '\n' ' ')"; tail -n 3 "$W/runs.log" | cut -c1-200
grep -E "bb-200v64|bg-200|BEN \(200\)" "$W/runs.log" | grep -E "end|servers" | tail -20 | cut -c1-120
echo "sps0b $(wc -l < "$W/runs/sps0b/results.jsonl") tables (final)"; date -u +%FT%TZ
