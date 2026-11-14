# boxctl: timeout=300
# boxctl: timeout=300
# loop session (Max, 06:22 UTC on 14 November: grade only on blind opponents): azure3's non-blind BEN session (jobs-azure3-ben5.txt)
# is stopped where it stands (finished boards kept) and the waiting switch with it; a new BEN session plays the blind gate
# (jobs-azure3-ben7.txt, source 9f18993) in a unit of its own, and at its end the test queue and Gen 8 records (jobs-azure3.txt).
set -euo pipefail
COMMIT=9f1899325815367516ae38bb62c015d22c43d9e4
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
tail -n 2 "$W/runs.log" | cut -c1-150
sudo systemctl stop loop-switch loop-bensession 2>/dev/null || true
for u in $(systemctl list-units --plain --no-legend 'loop-ben-*' | awk '{print $1}'); do sudo systemctl stop "$u"; done
sudo systemctl stop loop-chain loop-collect-b 2>/dev/null || true
pkill -u "$USER" -f scripts/x8_match.py 2>/dev/null || true; sleep 5
for r in b3-ps200b b3-pst200c b3-ps200c; do printf '%s: %s boards | ' $r "$(cat "$W"/runs/$r-[1-8]/results.jsonl 2>/dev/null | wc -l)"; done; echo
echo "$(date -u +%FT%TZ) the non-blind BEN session (jobs-azure3-ben5.txt) stopped by hand: the gate is blind from here (Max, 06:22 UTC)" >> "$W/runs.log"
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
sudo systemctl reset-failed loop-bensession 2>/dev/null || true
sudo systemd-run --unit=loop-bensession --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$S/$T/ben_session.sh" jobs-azure3-ben7.txt azure3
sleep 90; systemctl is-active loop-bensession loop-chain | tr '\n' ' '; tail -n 3 "$W/runs.log" | cut -c1-170; pgrep -u "$USER" -fc scripts/x8_match.py || true; date -u +%FT%TZ
