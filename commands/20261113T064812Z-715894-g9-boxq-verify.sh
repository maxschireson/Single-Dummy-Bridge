# boxctl: timeout=30
git -C ~/work/g9/channel log --oneline -1; grep -c "count == \"files\"" ~/work/g9/channel/tools/boxq.py; systemctl is-active g9-boxq g9-job-g9-cohort-azure4
