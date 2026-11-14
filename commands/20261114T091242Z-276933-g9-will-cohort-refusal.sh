# boxctl: timeout=120
sudo -n journalctl -u g9-job-g9-cohort-azure4 --since "09:07" --no-pager | cut -c1-260 | grep -vE "oneDNN|cpu_feature|TF_ENABLE" | head -40; systemctl is-active g9-job-g9-cohort-azure4; cat $HOME/work/g9/runs/g9-cohort-azure4/.exit 2>/dev/null
