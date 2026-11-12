# boxctl: timeout=90
# Hold the self-play trial: the branch is being rebuilt on the source that also captures gap forks, and the cohort should be
# prepared once, from that. Stops the trial unit and any collector it started; deletes nothing.
S=$HOME/work/selfplay; RUN=$HOME/work/runs/gen7-phase1-selfplay-$BOXCTL_BOX
echo "before: selfplay-trial $(systemctl is-active selfplay-trial), arena-selfplay $(systemctl is-active arena-selfplay 2>/dev/null)"
tail -12 $S/trial.log | cut -c1-420
if [ -e "$RUN/manifest.json" ]; then touch "$RUN/STOP"; fi
sudo systemctl stop selfplay-trial 2>/dev/null
sleep 2
pkill -u "$(id -un)" -f "unittest discover -s tests" 2>/dev/null
pkill -u "$(id -un)" -f "ops/smoke_gen7.py --run $RUN" 2>/dev/null
echo "after: selfplay-trial $(systemctl is-active selfplay-trial), arena-selfplay $(systemctl is-active arena-selfplay 2>/dev/null)"
echo "run folder: $([ -e "$RUN" ] && echo "exists, $(ls $RUN/receipts 2>/dev/null | wc -l) boards, STOP $([ -e $RUN/STOP ] && echo yes || echo no)" || echo none)"
echo "phase 1 cohort: WATCHDOG_STOP $([ -e $HOME/work/runs/gen7-phase1-$BOXCTL_BOX/WATCHDOG_STOP ] && echo yes || echo no)"
echo "$(date -u +%T) held by the operator: rebuilding on the capture source" >> $S/trial.log
