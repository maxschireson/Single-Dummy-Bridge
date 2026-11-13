# boxctl: timeout=900
#!/bin/bash
# G9 (dave, 07:46): restart g9-cohort-azure4 in place at 6 cores / 5 workers. Step 1: drain it with STOP in its run
# folder, wait for the unit to end, check exit 0, then remove STOP so the retry resumes the same run.
set -u
R=~/work/g9/runs/g9-cohort-azure4
U=g9-job-g9-cohort-azure4
before=$(ls $R/run/receipts | wc -l)
touch $R/run/STOP; echo "STOP at $(date -u +%T), receipts $before"
for i in $(seq 1 120); do systemctl is-active --quiet $U || break; sleep 5; done
echo "unit $(systemctl is-active $U) at $(date -u +%T); exit $(cat $R/.exit 2>/dev/null); receipts $(ls $R/run/receipts | wc -l)"
if ! systemctl is-active --quiet $U && [ "$(cat $R/.exit 2>/dev/null)" = "0" ]; then rm -f $R/run/STOP; echo "STOP removed"; else echo "NOT removing STOP: check"; fi
ls $R/run | grep -i stop || echo "no STOP files in run"
