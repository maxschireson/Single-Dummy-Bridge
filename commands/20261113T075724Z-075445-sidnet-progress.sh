# boxctl: timeout=120
cat ~/work/sidnet/logs/timeline.log; tail -3 ~/work/sidnet/logs/label.log | cut -c1-200; ls ~/work/sidnet/labels | wc -l; wc -l < ~/work/sidnet/labels/errors.jsonl; uptime | sed "s/.*load/load/"; free -g | sed -n 2p; du -sh ~/work/sidnet/eps ~/work/sidnet/labels | tr "\n" " "
