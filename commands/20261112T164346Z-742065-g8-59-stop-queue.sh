# boxctl: timeout=60
# boxctl: timeout=60
# g8 (azure1): my match queue unit is still loaded here, with nothing queued since my matches ended this morning. Show
# what it is doing and stop it, so it can never start anything on g7's box. Only g8-queue is touched.
echo "g8-queue: $(systemctl is-active g8-queue.service), since $(systemctl show g8-queue.service -p ActiveEnterTimestamp --value)"
for p in $(pgrep -u "$(id -un)" -f 'work/g8'); do echo "  pid $p: $(ps -o etimes=,pcpu=,rss= -p $p | awk '{print "up " $1 "s, cpu " $2 "%, rss " int($3/1024) " MB"}') | $(tr '\0' ' ' < /proc/$p/cmdline | cut -c1-160)"; done
ls -la "$HOME/work/g8/queue" 2>/dev/null | tail -5
sudo systemctl stop g8-queue.service 2>&1 | tail -1
sleep 2
echo "after: g8-queue $(systemctl is-active g8-queue.service 2>/dev/null); g8 units: $(systemctl list-units 'g8-*' --all --no-legend 2>/dev/null | awk '{print $1 "=" $3 "/" $4}' | tr '\n' ' '); g8 processes left: $(pgrep -u "$(id -un)" -f 'work/g8' -c 2>/dev/null)"
