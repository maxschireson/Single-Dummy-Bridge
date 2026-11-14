# boxctl: timeout=60
sudo -n journalctl -u g9-job-e9-25 --no-pager -n 30 2>&1 | cut -c1-400 | tail -30
