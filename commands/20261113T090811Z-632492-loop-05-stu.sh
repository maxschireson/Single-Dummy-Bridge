# boxctl: timeout=900
# boxctl: timeout=900
# loop session: the bot is Stu (Max, 09:05 UTC). Report the drain, stop the job chain (its gate match ran under the old id
# and is left on disk), check out the new bot file and start the chain again from the branch's job file.
set -euo pipefail
COMMIT=29d2e6a974c06d154011911f59fb01ddbb076dbb
W=$HOME/work/loop; S=$W/src; PY=$W/venv/bin/python; T=$S/training/rollout-loop-20261113
echo "== drain log"; tail -n 14 "$W/drain.log" | cut -c1-210
echo "== lanes"; for n in 1 2 3 4 5 6 7 8; do printf "%s:%s/%s " $n "$(systemctl is-active arena-ben@$n)" "$(systemctl is-active arena-ben-publish@$n)"; done; echo; echo "drain unit: $(systemctl is-active loop-drain || true)"
sudo systemctl stop loop-chain || true
echo "g0-v2 (id z0a-v2) stopped at $(wc -l < "$W/runs/g0-v2/results.jsonl") boards: $(tail -n 1 "$W/runs/g0-v2.log" | cut -c1-120)"
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-120
rm -f "$W/cap1-bots.json" "$W/cap2-bots.json" "$W/jobs.txt"
sudo systemctl reset-failed loop-chain 2>/dev/null || true
sudo systemd-run --unit=loop-chain --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$T/chain.sh" "$T/jobs-azure3.txt"
sleep 45; systemctl is-active loop-chain loop-publish | tr '\n' ' '; echo; tail -n 2 "$W/runs.log" | cut -c1-200; tail -n 2 "$W/runs/g0-stu0.log" 2>/dev/null | cut -c1-200; git -C "$W/pub" log -1 --format='publisher last pushed %cd' --date=format:'%H:%M UTC' 2>/dev/null; free -g | sed -n 2p; uptime; date -u +%FT%TZ
