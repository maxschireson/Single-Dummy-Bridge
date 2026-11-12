# boxctl: timeout=200
P=$HOME/work/p41; G=$HOME/work/g8p41; sudo systemd-run --unit=g8-report-t1 --uid="$(id -un)" --working-directory="$G" --setenv=HOME="$HOME" -- /bin/bash $P/report.sh t1 2>&1 | tail -1; sleep 100; tail -2 $P/logs/timeline.log; head -3 $P/runs/reading_reports/t1.txt | cut -c1-300; ps -eo etimes,pcpu,args | grep compare_nets | grep -v grep | cut -c1-120
