# boxctl: timeout=120
tail -1 ~/work/sidnet/logs/label.log | cut -c1-200; wc -l < ~/work/sidnet/labels/errors.jsonl; systemctl is-active sidnet-run sidnet-run2 | tr "\n" " "; uptime | sed "s/.*load/load/"; du -sh ~/work/sidnet/labels | cut -f1
