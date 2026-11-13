# boxctl: timeout=1800
# boxctl: timeout=1800
# sidplay: update the play server to 208403c13e1e80e4ca07f404b750b144bb3e860f (stand-in label, Sid entry point) and play two boards through its API.
set -euo pipefail
curl -fsSL https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/208403c13e1e80e4ca07f404b750b144bb3e860f/play/deploy/install.sh -o /tmp/sidplay-install.sh
bash /tmp/sidplay-install.sh 208403c13e1e80e4ca07f404b750b144bb3e860f 792c4cb3f647ec71273f0cc57d95be1d0a0a5954 8s-32.json 2>&1 | grep -v -E "^(WARNING|I0000|E0000|To enable)" | tail -12
timeout 900 python3 /opt/sidplay/app/play/smoke.py http://127.0.0.1:8090 --boards 2 --sid
systemctl show sidplay -p MemoryCurrent -p Nice
ps -o pid,ni,rss,etime,cmd -u sidplay | cut -c1-120
