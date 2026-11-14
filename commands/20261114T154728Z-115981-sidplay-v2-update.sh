# boxctl: timeout=3600
# boxctl: timeout=3600
# sidplay: update the play server to 29c4cc008948aa8b1fa14bc20635207b219bfc5a (analysis, Sid in your seat, replays; Sid = SiD (rollout) Stu R4c). Max, 14 Nov.
set -euo pipefail
echo "== before"; curl -fsS --noproxy '*' http://127.0.0.1:8090/api/health || true; echo
curl -fsSL https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/29c4cc008948aa8b1fa14bc20635207b219bfc5a/play/deploy/install.sh -o /tmp/sidplay-install.sh
bash /tmp/sidplay-install.sh 29c4cc008948aa8b1fa14bc20635207b219bfc5a a42fe6c1f9f66c17a8889e66a9d2542b60b32646 stu4c-put.json 2>&1 | grep -v -E "^(WARNING|I0000|E0000|To enable)" | tail -40
echo "== smoke"
timeout 1500 /opt/sidplay/venv/bin/python /opt/sidplay/app/play/smoke.py http://127.0.0.1:8090 --boards 1 --sid --analysis --timeout 1400
systemctl show sidplay -p MemoryCurrent -p Nice
ps -o pid,ni,rss,etime,cmd -u sidplay | cut -c1-140
free -m | head -2
