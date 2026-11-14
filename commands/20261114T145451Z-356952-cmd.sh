# boxctl: timeout=600
# loop session: round 4's gate on azure3 (Max, 04:23 and 06:22 UTC: the gate is on BEN, blind; 09:39: an R4a and an R4b).
# Round 4's net with the USBC's human tables is fetched (get_net.sh 4); a BEN session plays jobs-azure3-ben8.txt (stu4-put,
# then the control stu4c-put, in turns on the deals the one-net SiD R3 played blind), and at its end goes back to the
# test queue (jobs-azure3.txt). The control's net is fetched when it is trained (before its first block's turn).
set -euo pipefail
COMMIT=830661d; SHA4=edc5d6cfaf9fd868e4e07708b18ad6e712da1cf981688b1a152857ace5d8853f
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
tail -n 3 "$W/runs.log" | cut -c1-150
for r in bu3-pst200a bu3-pst200b bu3-pst200c bu3-pst200d bu3-pst200e; do printf '%s: %s boards | ' $r "$(cat "$W"/runs/$r-[1-8]/results.jsonl 2>/dev/null | wc -l)"; done; echo
sudo systemctl stop loop-switch loop-bensession 2>/dev/null || true
for u in $(systemctl list-units --plain --no-legend 'loop-ben-*' | awk '{print $1}'); do sudo systemctl stop "$u"; done
sudo systemctl stop loop-chain loop-collect-b 2>/dev/null || true
pkill -u "$USER" -f scripts/x8_match.py 2>/dev/null || true; sleep 5
echo "$(date -u +%FT%TZ) round 4's gate begins: the box's chains stop; jobs-azure3-ben8.txt in a BEN session" >> "$W/runs.log"
git -C "$S" fetch -q --depth 12 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
cd "$S"; bash $T/get_net.sh 4 "$SHA4"
sudo systemctl reset-failed loop-bensession 2>/dev/null || true
sudo systemd-run --unit=loop-bensession --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$S/$T/ben_session.sh" jobs-azure3-ben8.txt azure3
sleep 100; systemctl is-active loop-bensession loop-chain | tr '\n' ' '; tail -n 3 "$W/runs.log" | cut -c1-170; pgrep -u "$USER" -fc scripts/x8_match.py || true; date -u +%FT%TZ
