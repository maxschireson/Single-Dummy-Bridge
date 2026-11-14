# boxctl: timeout=3600
# boxctl: timeout=3600
# sidplay: update to e7f61d7450f1e0fd3853d1b153d224efec8d3b74 (the analysis reads the auction: Sid's scorer + cell game). Max, 14 Nov 09:08 PST.
set -euo pipefail
echo "== before"; curl -fsS --noproxy '*' http://127.0.0.1:8090/api/health || true; echo
curl -fsSL https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/e7f61d7450f1e0fd3853d1b153d224efec8d3b74/play/deploy/install.sh -o /tmp/sidplay-install.sh
bash /tmp/sidplay-install.sh e7f61d7450f1e0fd3853d1b153d224efec8d3b74 a42fe6c1f9f66c17a8889e66a9d2542b60b32646 stu4c-put.json 2>&1 | grep -v -E "^(WARNING|I0000|E0000|To enable)" | tail -25
echo "== smoke (public name: secure cookies)"
timeout 1500 /opt/sidplay/venv/bin/python /opt/sidplay/app/play/smoke.py https://play-sid.eastus.cloudapp.azure.com --boards 1 --sid --analysis --timeout 1400
sudo -u sidplay /opt/sidplay/venv/bin/python - <<'PY'
import sqlite3, json, glob
db = sqlite3.connect(sorted(glob.glob('/var/lib/sidplay/*.sqlite'))[0])
bid, a, sa = db.execute('SELECT id, analysis, sid_analysis FROM boards ORDER BY id DESC LIMIT 1').fetchone()
for name, x in (('you', a), ('sid', sa)):
    if x:
        e = json.loads(x)['engines']
        print(bid, name, {k: e.get(k) for k in ('auction', 'auction_decisions', 'auction_seconds', 'seconds')})
PY
systemctl show sidplay -p MemoryCurrent
