# boxctl: timeout=3600
# boxctl: timeout=3600
# sidplay: install the play-against-Sid server (PR #33) on this box, 127.0.0.1:8090 only. Max, 13 Nov 05:58 UTC.
set -euo pipefail
curl -fsSL https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/6723aa2a60948f6cc1b2227e44a39cb7223fb0ee/play/deploy/install.sh -o /tmp/sidplay-install.sh
bash /tmp/sidplay-install.sh 6723aa2a60948f6cc1b2227e44a39cb7223fb0ee 792c4cb3f647ec71273f0cc57d95be1d0a0a5954 8s-32.json 2>&1 | grep -v -E "^(WARNING|I0000|E0000|To enable)" | tail -60
systemctl --no-pager status sidplay | head -12
free -m | head -2
