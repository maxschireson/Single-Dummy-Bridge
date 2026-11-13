# boxctl: timeout=180
# boxctl: timeout=180
# plan session: azure2: release. match2 ended at 15:12; stop my queue runner and publisher after one last publish.
# Files stay under ~/work/plan (rollout net v2's set is read by sidnet and loop).
set -uo pipefail
P=$HOME/work/plan
tail -2 $P/queue.log | cut -c1-100; echo "pos $(cat $P/queue.pos) of $(wc -l < $P/queue.txt)"
systemctl list-units --no-pager 'plan-*' 2>/dev/null | grep plan- | cut -c1-100
sleep 90       # let the publisher's next push carry the last files
for u in plan-queue plan-publish; do sudo -n systemctl stop $u 2>&1 && echo "stopped $u" || echo "could not stop $u"; done
systemctl list-units --no-pager 'plan-*' 2>/dev/null | grep plan- | cut -c1-100
ps aux | grep -c "[p]lan_match\|[q]ueue.sh"; du -sh $P 2>/dev/null; uptime
