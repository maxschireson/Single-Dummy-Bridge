# boxctl: timeout=1800
# boxctl: timeout=3600
# sidplay: update to 26cc9e3025509a8f68c5ae1ba734187b3a23401a with source 109a21c74730749bb6c6bfe16cac78bf04120bd9 (Sid's personalities, SidVariable). Max, 14 Nov 13:14 PST.
set -euo pipefail
echo "== before"; curl -fsS --noproxy '*' http://127.0.0.1:8090/api/health || true; echo
curl -fsSL https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/26cc9e3025509a8f68c5ae1ba734187b3a23401a/play/deploy/install.sh -o /tmp/sidplay-install.sh
bash /tmp/sidplay-install.sh 26cc9e3025509a8f68c5ae1ba734187b3a23401a 109a21c74730749bb6c6bfe16cac78bf04120bd9 stu4c-put.json 2>&1 | grep -v -E "^(WARNING|I0000|E0000|To enable)" | tail -25
echo "== smoke (public name: secure cookies)"
echo skip smoke
sudo -u sidplay /opt/sidplay/venv/bin/python - <<'PY'
import sqlite3, json, glob
db = sqlite3.connect(sorted(glob.glob('/var/lib/sidplay/*.sqlite'))[0])
bid, ps, sid = db.execute('SELECT id, personas, sid_table FROM boards ORDER BY id DESC LIMIT 1').fetchone()
ps = json.loads(ps) if ps else None
print(bid, 'personas seats', sorted(ps) if ps else None, 'E bid style', ps and ps['1']['bid_style'], 'sid table', bool(sid))
PY
systemctl show sidplay -p MemoryCurrent
journalctl -u sidplay --since "-20 min" --no-pager | grep -E "Traceback|Error|failed" | grep -v cuInit | tail -10 || true
