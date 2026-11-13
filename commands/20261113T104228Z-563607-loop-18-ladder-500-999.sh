# boxctl: timeout=900
# boxctl: timeout=900
# loop session: azure5 plays the ladder's deciding comparison on deals 500 to 999 (Stu, then the bot with no double dummy,
# each against Gen 8 card play; azure3 plays deals 0 to 499), then goes back to the collection. The collection's boards
# are kept and it resumes where it stopped.
set -euo pipefail
COMMIT=0723f0b4979845e0e048190b6061cb223c1411b2
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
sudo systemctl stop loop-collect || true
echo "s0 paused at $(wc -l < "$W/runs/s0/results.jsonl") boards: $(tail -n 1 "$W/runs/s0.log" | cut -c1-100)"
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-110
sudo systemctl reset-failed loop-collect 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure5.txt"
sleep 45; systemctl is-active loop-collect loop-publish | tr '\n' ' '; echo; tail -n 2 "$W/runs.log" | cut -c1-150; tail -n 1 "$W/runs/l0b-stu0.log" 2>/dev/null | cut -c1-120; ls "$W/pub" | tr '\n' ' '; echo; date -u +%FT%TZ
