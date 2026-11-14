# boxctl: timeout=3600
# boxctl: timeout=3600
# sidplay: update to 4bb484f3080c91e72ad85ad02f34a8e1a9a2558e with source 109a21c74730749bb6c6bfe16cac78bf04120bd9 (Sid's personalities, SidVariable). Max, 14 Nov 13:14 PST.
set -euo pipefail
echo "== before"; curl -fsS --noproxy '*' http://127.0.0.1:8090/api/health || true; echo
curl -fsSL https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/4bb484f3080c91e72ad85ad02f34a8e1a9a2558e/play/deploy/install.sh -o /tmp/sidplay-install.sh
bash /tmp/sidplay-install.sh 4bb484f3080c91e72ad85ad02f34a8e1a9a2558e 109a21c74730749bb6c6bfe16cac78bf04120bd9 stu4c-put.json 2>&1 | grep -v -E "^(WARNING|I0000|E0000|To enable)" | tail -25
echo "== personas on?"
curl -fsS --noproxy '*' https://play-sid.eastus.cloudapp.azure.com/api/me | head -c 900; echo
echo "== smoke (public name: secure cookies)"
timeout 1500 /opt/sidplay/venv/bin/python /opt/sidplay/app/play/smoke.py https://play-sid.eastus.cloudapp.azure.com --boards 1 --sid --analysis --timeout 1400
sudo -u sidplay /opt/sidplay/venv/bin/python - <<'PY'
import sqlite3, json, glob
db = sqlite3.connect(sorted(glob.glob('/var/lib/sidplay/*.sqlite'))[0])
bid, ps, sid = db.execute('SELECT id, personas, sid_table FROM boards ORDER BY id DESC LIMIT 1').fetchone()
ps = json.loads(ps) if ps else None
print(bid, 'personas seats', sorted(ps) if ps else None, 'E bid style', ps and ps['1']['bid_style'], 'sid table', bool(sid))
PY
systemctl show sidplay -p MemoryCurrent
journalctl -u sidplay --since "-20 min" --no-pager | grep -E "Traceback|Error|failed" | grep -v cuInit | tail -10 || true
