# loop session: read how azure3's lanes are recycled and switched (read-only), to drain them as g7's own scripts do
for u in lane-recycle lane-switch arena-ben@ arena-ben-publish@ ben-server@ g8-queue g8-publish; do echo "=== unit $u"; systemctl cat "$u.service" 2>/dev/null | grep -v "^#" | head -40; done
echo "=== lanes dir: non-numbered files"; ls -la ~/work/lanes | grep -v -E " [1-8]\.[a-z]" | head -40
for f in $(systemctl cat lane-recycle.service lane-switch.service 2>/dev/null | grep -E "^ExecStart" | sed -E 's/^ExecStart=//' | tr ' ' '\n' | grep -E "^/" | sort -u); do echo "=== file $f"; [ -f "$f" ] && head -c 6000 "$f"; done
echo "=== g8 queue"; tail -n 5 ~/work/g8/queue.log 2>/dev/null | cut -c1-250; cat ~/work/g8/queue.pos 2>/dev/null; wc -l ~/work/g8/queue.txt 2>/dev/null
echo "=== lane states"; for n in 1 2 3 4 5 6 7 8; do echo "lane $n: $(grep -E 'COHORT|RUN|POOL|NAME' ~/work/lanes/$n.env 2>/dev/null | tr '\n' ' ' | cut -c1-230)"; tail -n 1 ~/work/lanes/$n.collector.log | cut -c1-200; done
