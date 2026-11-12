# boxctl: timeout=120
# p41: Max did not ask for the continuation run (he was asking why, not for a change). Stop it and its scoring; the two five-epoch
# runs go on as before. Nothing else is touched.
set -uo pipefail
P=$HOME/work/p41
sudo systemctl stop p41-w512c1 p41-eval-w512c1 2>/dev/null; sudo systemctl reset-failed p41-w512c1 p41-eval-w512c1 2>/dev/null
sleep 2; pgrep -af "runs/w512c1" | grep -v pgrep | wc -l
rm -rf $P/runs/w512c1; echo "w512c1 stopped and removed (not asked for) $(date -u +%T)" >> $P/logs/timeline.log
systemctl is-active p41-w512e5 p41-w768e5 p41-eval-w512e5 p41-eval-w768e5 | tr '\n' ' '; echo
tail -3 $P/logs/timeline.log; tail -n +3 $P/logs/w512e5.out | cut -c1-330; tail -1 $P/logs/w512e5.err; tail -n +2 $P/logs/w768e5.out | cut -c1-330; tail -1 $P/logs/w768e5.err
