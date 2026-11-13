# boxctl: timeout=60
R=~/work/g9/runs; ls -la $R/g9-cohort-azure4/run/dds-cache.sqlite* $R/g9-cohort-ben64-azure4/run/dds-cache.sqlite* 2>&1 | awk "{print \$5, \$NF}"; df -h /dev/shm | tail -1; grep -n "dds-cache\|synchronous\|journal_mode\|DDS_CACHE" ~/work/g9/src/46b7e004/ops/gen5_runtime.py ~/work/g9/src/46b7e004/bridge_harness/*.py 2>/dev/null | head -8
