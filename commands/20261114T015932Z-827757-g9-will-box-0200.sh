# boxctl: timeout=120
R=$HOME/work/g9/runs; for j in g9-cohort-azure4 g9-cohort-ben64-azure4; do n=$(ls $R/$j/run/receipts | wc -l); h=$(find $R/$j/run/receipts -name "*.json" -mmin -60 | wc -l); echo "$j $n last60=$h"; done; df -h --output=avail $HOME | tail -1; du -sh $R/g9-cohort-azure4/run/dds-cache.sqlite* 2>/dev/null; iostat -dx 5 2 | grep nvme0n1 | tail -1; vmstat 5 2 | tail -1
