# boxctl: timeout=60
R=$HOME/work/g9/runs/g9-cohort-azure4/run; ls $R/receipts | wc -l; touch $R/STOP; ls -la $R/STOP; systemctl --user list-units "g9-job-*" --no-legend 2>/dev/null | head; ps -eo pid,etimes,args | grep -E "gen5_runtime|run_gen9_cohort" | grep -v grep | cut -c1-160
