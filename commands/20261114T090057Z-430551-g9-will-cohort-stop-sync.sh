# boxctl: timeout=60
R=$HOME/work/g9/runs/g9-cohort-azure4/run; ls $R/receipts | wc -l; touch $R/STOP; ls -la $R/STOP; iostat -dx 10 2 | grep nvme0n1 | tail -1 | awk "{print \"before: w/s\",\$8,\"w_await\",\$12,\"f/s\",\$(NF-3),\"util\",\$NF}"
