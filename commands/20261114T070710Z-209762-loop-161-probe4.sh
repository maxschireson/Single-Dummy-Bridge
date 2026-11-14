# boxctl: timeout=120
# boxctl: timeout=120
# loop session (read-only): the auction in a table's FULL event; ids of later USBCs (2025: screen 631412).
set -uo pipefail
cd $HOME/work/usbc/probe
UA="Mozilla/5.0 (research; USBF records for bot evaluation)"; B=https://vugraph.lovebridge.com
python3 - <<'PY'
import json
e = json.load(open('w_400345.json'))
f = e[0]['payload']; print(sorted(f))
for k in f:
    s = json.dumps(f[k])
    if k not in ('ps', 'tmDto'): print(k, s[:300])
for x in e:
    if x['tt'] in ('CLAIM', 'CLAIM_ACCEPT', 'END_GAME', 'END_AUCTION'): print(x)
PY
for id in usbc_631412_1_1 usbc_631412_2_1 usbc_631412_1_2; do curl -sS -m 20 -A "$UA" "$B/api/archive/boards/$id" -o p.json -w "%{http_code} %{size_download} $id\n"; done
curl -sS -m 20 -A "$UA" "$B/screen/usbc/631412?screen=running-score" -o s.html -w "%{http_code}\n"; grep -o -E "usbc_[0-9_]+" s.html | sort -u | head
