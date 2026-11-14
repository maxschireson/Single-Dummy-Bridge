# boxctl: timeout=60
R=$HOME/work/g9/runs; rm -f $R/g9-cohort-azure4/run/STOP; ls $R/g9-cohort-azure4/run/STOP 2>&1; cat $R/g9-cohort-azure4/.exit; ls $R/g9-cohort-azure4/run/receipts | wc -l; ls $R/g9-cohort-azure4/run/failures | wc -l; echo ---e9-25; cat $R/e9-25/.exit 2>/dev/null; ls $R/e9-25/ 2>/dev/null; tail -25 $R/e9-25/*.log 2>/dev/null | tail -30
