# boxctl: timeout=60
R=$HOME/work/g9/runs/g9-cohort-azure4; rm -f $R/run/STOP; ls $R/run/STOP 2>&1 | tail -1; cat $R/.exit; ls $R/run/receipts | wc -l; ls $R/run/failures | wc -l
