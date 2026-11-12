# boxctl: timeout=120
journalctl -u g9-job-d6-arrival --no-pager -o short-iso 2>/dev/null | grep -v -i "pam_unix\|sudo\[" | tail -120 | cut -c1-400
echo "== exit file"; cat ~/work/g9/runs/d6-arrival/.exit 2>/dev/null
echo "== results"; wc -l ~/work/g9/runs/d6-arrival/results.jsonl; ls ~/work/g9/runs/d6-arrival/control/results/
for f in ~/work/g9/runs/d6-arrival/control/results/e*/slot0.jsonl; do echo "$f $(wc -l < $f)"; done
ls -la ~/work/g9/runs/d6-arrival/control/ | head; cat ~/work/g9/runs/d6-arrival/control/CURRENT 2>/dev/null | head -c 300; echo
free -g | head -2; df -h ~/work | tail -1; dmesg 2>/dev/null | grep -i -E "oom|killed process" | tail -5
