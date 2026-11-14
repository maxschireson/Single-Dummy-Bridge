# boxctl: timeout=300
# boxctl: timeout=300
# loop session (Max, 05:14 UTC on 14 November: does one-net R3 improve over one-net R0 against BEN?): azure5 joins the gate. A
# unit of its own (loop-next) waits for the match in hand (h3-pib) to finish, stops the queue behind it, checks BEN here against
# azure3's (ben_install.sh; installs it if the box has none), plays jobs-azure5-ben.txt through ben_session.sh, and then the queue that
# was waiting (jobs-azure5-v41-styles.txt; finished matches are skipped).
set -euo pipefail
COMMIT=ba98377a97536e1324546da77831c2e9d86816ab
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
cat > "$W/next-ben.sh" <<EOS
#!/usr/bin/env bash
while [ "\$(cat "$W/runs/h3-pib/results.jsonl" 2>/dev/null | wc -l)" -lt 500 ] && [ "\$(systemctl is-active loop-rungs2)" = active ]; do sleep 15; done
sudo systemctl stop loop-rungs2 loop-rungs 2>/dev/null; sudo systemctl stop loop-collect loop-collect-b 2>/dev/null
pkill -u "$USER" -f scripts/x8_match.py 2>/dev/null; sleep 5
echo "\$(date -u +%FT%TZ) azure5 joins the gate: jobs-azure5-ben.txt, then jobs-azure5-v41-styles.txt" >> "$W/runs.log"
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" checkout -q $COMMIT
if bash "$S/$T/ben_install.sh" | grep -q 'BEN install: PASS'; then
  bash "$S/$T/ben_session.sh" jobs-azure5-ben.txt azure5
else
  echo "\$(date -u +%FT%TZ) BEN on azure5 did not pass its check: jobs-azure5-ben.txt not played" >> "$W/runs.log"
fi
bash "$S/$T/rungs.sh" jobs-azure5-v41-styles.txt azure5
EOS
sudo systemctl reset-failed loop-next 2>/dev/null || true
sudo systemd-run --unit=loop-next --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/next-ben.sh"
sleep 5; echo "units: rungs $(systemctl is-active loop-rungs || true) rungs2 $(systemctl is-active loop-rungs2 || true) next $(systemctl is-active loop-next || true)"
tail -n 1 "$W/runs.log" | cut -c1-170; echo "h3-pib boards: $(cat "$W/runs/h3-pib/results.jsonl" 2>/dev/null | wc -l)"; ls -d "$HOME/work/ben" "$HOME/work/ben-venv" 2>/dev/null | tr '\n' ' '; date -u +%FT%TZ
