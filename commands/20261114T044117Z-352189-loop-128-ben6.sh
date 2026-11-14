# boxctl: timeout=300
# boxctl: timeout=300
# loop session (Max, 04:30 UTC on 14 November: "We should run more Ben compare deals"): azure6 joins the gate. A unit of its
# own (loop-next) waits for the blind match in hand (l3-pu) to finish, stops the queue behind it (l3-pux, then h3-pm), plays
# jobs-azure6-ben.txt against BEN (200) through ben_session.sh, and then the cost of our own randomization (jobs-azure6-mix.txt).
# The BEN install is checked first (ben_install.sh: must say PASS).
set -euo pipefail
COMMIT=a0bc029c0fa105f1fc1ac1d5820003b7a68b52b6
W=$HOME/work/loop; S=$W/src; S2=$W/src-lc; T=training/rollout-loop-20261113
[ -d "$S2/.git" ] || git clone -q --depth 5 --branch research/rollout-loop-20261113 https://github.com/maxschireson/Single-Dummy-Bridge "$S2"
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q "$COMMIT"
nice -n 10 bash "$S2/$T/ben_install.sh" | tail -n 6
cat > "$W/next-ben.sh" <<EOS
#!/usr/bin/env bash
while [ "\$(cat "$W/runs/l3-pu/results.jsonl" 2>/dev/null | wc -l)" -lt 500 ] && [ "\$(systemctl is-active loop-rungs2)" = active ]; do sleep 15; done
sudo systemctl stop loop-rungs3 loop-rungs2 loop-rungs 2>/dev/null; sudo systemctl stop loop-collect loop-collect-b 2>/dev/null
pkill -u "$USER" -f scripts/x8_match.py 2>/dev/null; sleep 5
echo "\$(date -u +%FT%TZ) azure6 joins the gate: l3-pux stopped at \$(cat "$W/runs/l3-pux/results.jsonl" 2>/dev/null | wc -l) boards; jobs-azure6-ben.txt, then jobs-azure6-mix.txt" >> "$W/runs.log"
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" checkout -q $COMMIT
bash "$S/$T/ben_session.sh" jobs-azure6-ben.txt azure6
bash "$S/$T/rungs.sh" jobs-azure6-mix.txt azure6
EOS
sudo systemctl reset-failed loop-next 2>/dev/null || true
sudo systemd-run --unit=loop-next --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/next-ben.sh"
sleep 5; echo "units: rungs $(systemctl is-active loop-rungs || true) rungs2 $(systemctl is-active loop-rungs2 || true) rungs3 $(systemctl is-active loop-rungs3 || true) next $(systemctl is-active loop-next || true)"
tail -n 2 "$W/runs.log" | cut -c1-170; echo "l3-pu boards: $(cat "$W/runs/l3-pu/results.jsonl" 2>/dev/null | wc -l)"; ls "$HOME/work/lanes" 2>/dev/null | head -3 | tr '\n' ' '; date -u +%FT%TZ
