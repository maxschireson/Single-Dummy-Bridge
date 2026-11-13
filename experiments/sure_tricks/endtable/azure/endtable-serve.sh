# Ending-table copy: serve ~/work/endtable/tables read-only on the private address only, for the other boxes to fetch.
# Unit endtable-serve stops itself after 30 minutes.
set -euo pipefail
D=$HOME/work/endtable/tables
cd "$D" && sha256sum k1.et k2.et k3.et k4.et > SHA256SUMS && cat SHA256SUMS
systemctl is-active --quiet endtable-serve && sudo systemctl stop endtable-serve
sudo systemctl reset-failed endtable-serve 2>/dev/null || true
sudo systemd-run --unit=endtable-serve --uid="$(id -un)" --property=RuntimeMaxSec=1800 -- python3 -m http.server --bind 172.16.0.9 --directory "$D" 8765
sleep 2
systemctl is-active endtable-serve
curl -s -o /dev/null -w "local fetch of SHA256SUMS: %{http_code}\n" http://172.16.0.9:8765/SHA256SUMS
