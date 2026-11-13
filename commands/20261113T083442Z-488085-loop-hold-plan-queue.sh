# loop session (Max, 08:23 UTC 13 Nov: "Take azure 3 and 5"): hold plan's queue where it stands, killing nothing.
# queue.sh (the unit's main process) is frozen with SIGSTOP. Its running job (rbc2a) is a child and runs on to its end;
# the queue then cannot start the next line (rbc2b) until it is continued:
#   sudo kill -CONT <pid below>      (or: sudo systemctl kill --kill-whom=main --signal=SIGCONT plan-queue.service)
# plan-publish keeps pushing plan's outputs. No file of plan's is changed.
set -u
PID=$(systemctl show -p MainPID --value plan-queue.service)
echo "plan-queue main pid: $PID ($(ps -o args= -p "$PID" | cut -c1-80))"
[ -n "$PID" ] && [ "$PID" != 0 ] && sudo kill -STOP "$PID"
sleep 1
ps -o pid,stat,etimes,args -p "$PID" | cut -c1-120
echo "queue.pos $(cat ~/work/plan/queue.pos); last log: $(tail -n 1 ~/work/plan/queue.log | cut -c1-120)"
echo "children still running: $(pgrep -f plan_reading_bound.py | wc -l) plan_reading_bound.py processes"
date -u +%FT%TZ
