# boxctl: timeout=300
# boxctl: timeout=300
# loop session: azure6 publishes its collection's training rows in blocks of 1,000 boards (unit loop-rows, Nice 10, two
# workers), for round training on azure5. The checkout only adds files and changes round2.sh; the chains are not stopped.
set -euo pipefail
COMMIT=3c4e498ee9411df62e53f19af6f8f3bb3ea94c9a
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" | tail -5
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
sudo systemctl stop loop-rows 2>/dev/null || true; sudo systemctl reset-failed loop-rows 2>/dev/null || true
sudo systemd-run --unit=loop-rows --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$T/rows.sh" sp0c spr0c
sleep 8; systemctl is-active loop-collect loop-collect-b loop-publish loop-rows | tr '\n' ' '; echo
for r in sp0c spr0c; do echo "$r $(wc -l < "$W/runs/$r/results.jsonl" 2>/dev/null) tables"; done; date -u +%FT%TZ
