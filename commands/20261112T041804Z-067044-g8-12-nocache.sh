# boxctl: timeout=300
# boxctl: timeout=300
# g8: the eight workers sit at about 80% CPU each; the suspect is the shared SQLite cache of solved positions, which
# fresh random deals hardly ever hit. Turn it off for the Gen 8 queue only (an empty BRIDGE_DDS_CACHE disables it; the
# answers are the same either way) and restart the queue. The running match resumes where it was.
set -uo pipefail
G=$HOME/work/g8
grep -q '^export BRIDGE_DDS_CACHE=' "$G/queue.sh" || sed -i '0,/^cd "\$G\/src"/s//export BRIDGE_DDS_CACHE=\ncd "$G\/src"/' "$G/queue.sh"
grep -n 'BRIDGE_DDS_CACHE' "$G/queue.sh" | cut -c1-80
before=$(tail -1 "$G"/runs/$(ls -t "$G/runs" | grep '\.log$' | head -1) | cut -c1-120)
sudo systemctl restart g8-queue
echo "before: $before"
sleep 200
echo "after 200 s: $(tail -1 "$G"/runs/$(ls -t "$G/runs" | grep '\.log$' | head -1) | cut -c1-120)"
top -b -n 1 | grep python | head -8 | awk '{print $9}' | tr '\n' ' '; echo "(% CPU of the workers)"
uptime | sed 's/.*load/load/'
