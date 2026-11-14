# boxctl: timeout=180
# boxctl: timeout=180
# loop session: azure1's role switch did not fire (its wait pattern held a '|' that the launcher split, so grep failed and it
# waited on). Done by hand now: the collection (Gen 8 without personalities, from the BEN session's restart) stops, the source
# moves to 9f18993 and the box starts on Gen 8's personalities' self-play (jobs-azure1.txt). The row publisher is restarted with the new runs.
set -euo pipefail
COMMIT=9f1899325815367516ae38bb62c015d22c43d9e4
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
sudo systemctl stop loop-switch loop-collect loop-collect-b 2>/dev/null || true
pkill -u "$USER" -f scripts/x8_match.py 2>/dev/null || true; sleep 5
for r in sg8e sg8f; do [ -e "$W/runs/$r/results.jsonl" ] && echo "$r $(wc -l < "$W/runs/$r/results.jsonl") tables"; done
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
echo "$(date -u +%FT%TZ) azure1's role from here (Max, 05:24 and 05:37 UTC): Gen 8's personalities' self-play (jobs-azure1.txt, source ${COMMIT:0:7}); set by hand, the switch had not fired" >> "$W/runs.log"
sudo systemctl reset-failed loop-collect loop-collect-b 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$S/$T/chain.sh" "$S/$T/jobs-azure1.txt"
sudo systemd-run --unit=loop-collect-b --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$S/$T/chain.sh" "$S/$T/jobs-azure1b.txt"
if [ -n "sg8e sg8s1 sg8s2 sg8s3 sg8s4 sg8s5 sg8s6 sg8s7 sg8s8 sg8s9 sg8s10 sg8s11 sg8s12" ]; then
  sudo systemctl stop loop-rows 2>/dev/null || true; sudo systemctl reset-failed loop-rows 2>/dev/null || true
  sudo systemd-run --unit=loop-rows --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$S/$T/rows.sh" sg8e sg8s1 sg8s2 sg8s3 sg8s4 sg8s5 sg8s6 sg8s7 sg8s8 sg8s9 sg8s10 sg8s11 sg8s12
fi
sleep 30; echo "units: $(for u in loop-collect loop-collect-b loop-rows loop-switch; do printf '%s=%s ' $u $(systemctl is-active $u); done)"; tail -n 2 "$W/runs.log" | cut -c1-170; date -u +%FT%TZ
