# boxctl: timeout=1800
# boxctl: timeout=1800
# sidplay (read-mostly): one smoke board through the public HTTPS name (secure cookies), with Sid's table and both analyses.
set -euo pipefail
timeout 1500 /opt/sidplay/venv/bin/python /opt/sidplay/app/play/smoke.py https://play-sid.eastus.cloudapp.azure.com --boards 1 --sid --analysis --timeout 1400
systemctl show sidplay -p MemoryCurrent -p Nice
ps -o pid,ni,rss,etime,cmd -u sidplay | cut -c1-140
journalctl -u sidplay --since "-30 min" --no-pager | grep -E "Traceback|Error|failed" | grep -v cuInit | tail -10 || true
