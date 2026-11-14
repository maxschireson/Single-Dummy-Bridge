# boxctl: timeout=120
iostat -dx 15 3 | grep nvme0n1 | awk "{print \"w/s\",\$8,\"wkB/s\",\$9,\"w_await\",\$12,\"aqu\",\$(NF-1),\"util\",\$NF}"; vmstat 5 3 | tail -2; R=$HOME/work/g9/runs; for j in g9-cohort-azure4 g9-cohort-ben64-azure4 g9-genx-stu-azure4; do echo "$j $(ls $R/$j/run/receipts | wc -l) last15=$(find $R/$j/run/receipts -name "*.json" -mmin -15 | wc -l)"; done
