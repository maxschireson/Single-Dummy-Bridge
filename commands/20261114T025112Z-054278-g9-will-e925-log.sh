# boxctl: timeout=60
journalctl --user -u g9-job-e9-25 --no-pager -n 40 2>/dev/null | cut -c1-300 | tail -40; ls $HOME/work/g9/runs/e9-25/; ls $HOME/work/g9/runs/e9-25/*.log
