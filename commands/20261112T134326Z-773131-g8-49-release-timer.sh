# boxctl: timeout=60
# boxctl: timeout=60
# g8 (azure4): so that the box is free at 15:00 UTC whether or not my session is awake: my match queue and every other
# g8 unit stop at 14:58 UTC, the publisher makes its last push and stops at 15:06. Files stay under ~/work/g8.
set -uo pipefail
G=$HOME/work/g8
# the match after the running one is not to start here
pos=$(cat "$G/queue.pos"); head -n $((pos + 1)) "$G/queue.txt" > "$G/queue.new" && mv "$G/queue.new" "$G/queue.txt"
sudo systemctl stop g8-release g8-release.timer g8-release2 g8-release2.timer 2>/dev/null; sudo systemctl reset-failed g8-release g8-release2 2>/dev/null
sudo systemd-run --quiet --unit=g8-release --on-calendar='2026-11-12 14:58:00 UTC' /bin/sh -c 'systemctl stop g8-queue g8-final g8-states g8-states2 g8-tune-est g8-tables g8-tune 2>/dev/null; pkill -u bridgebots -f gen8_match.py; true'
sudo systemd-run --quiet --unit=g8-release2 --on-calendar='2026-11-12 15:06:00 UTC' /bin/sh -c 'systemctl stop g8-publish g8-publish.timer 2>/dev/null; true'
systemctl list-timers --no-pager 2>/dev/null | grep g8-release | cut -c1-150
echo "queue $(systemctl is-active g8-queue) at $(cat "$G/queue.pos") of $(wc -l < "$G/queue.txt"); publish $(systemctl is-active g8-publish 2>/dev/null) $(systemctl is-active g8-publish.timer 2>/dev/null); user $(id -un)"
wc -l "$G/runs/b1-8c-v-8a/results.jsonl" 2>/dev/null | cut -c1-60; date -u +%H:%M:%S
