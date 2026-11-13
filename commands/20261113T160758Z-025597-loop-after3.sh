# boxctl: timeout=300
# boxctl: timeout=300
# loop session: what azure3 does when the matches against BEN end (about 17:45): loop-switch restarts the chain on the
# new jobs-azure3.txt (the collection with the net's lead, six workers); the unit loop-after-ben then starts the second
# chain (rolled-out leads, two workers) and the rows publisher. The checkout changes job files that nothing has open
# (the BEN chain reads jobs-azure3-ben.txt), the bots file (one bot added) and adds scripts.
set -euo pipefail
COMMIT=b4eea94140909f67ff049218e200e8d70b3b5029
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" | tail -3
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
cat > "$W/after-ben.sh" <<'SH'
#!/bin/bash
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
until grep -q "the matches against BEN have ended" "$W/runs.log"; do sleep 30; done
sudo systemctl reset-failed loop-collect-b loop-rows 2>/dev/null
sudo systemd-run --unit=loop-collect-b --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure3b.txt"
sudo systemd-run --unit=loop-rows --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$T/rows.sh" sp0b spr0b
SH
sudo systemctl stop loop-after-ben 2>/dev/null || true; sudo systemctl reset-failed loop-after-ben 2>/dev/null || true
sudo systemd-run --unit=loop-after-ben --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/after-ben.sh"
sleep 3; systemctl is-active loop-switch loop-after-ben loop-ledger loop-publish | tr '\n' ' '; echo; grep -v '^#' "$T/jobs-azure3.txt" | tail -1
tail -n 9 "$W/runs.log" | cut -c1-120
for b in b0-p b0-g8 b0-stu0; do t=0; for n in 1 2 3 4 5 6 7 8; do t=$((t + $(wc -l < "$W/runs/$b-$n/results.jsonl" 2>/dev/null || echo 0))); done; echo "$b $t boards"; done; date -u +%FT%TZ
