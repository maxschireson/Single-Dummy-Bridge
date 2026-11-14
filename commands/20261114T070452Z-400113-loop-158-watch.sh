# boxctl: timeout=120
# boxctl: timeout=120
# loop session (read-only): one table's event log (auction and play) from the vugraph archive.
set -uo pipefail
D=$HOME/work/usbc/probe; cd $D
UA="Mozilla/5.0 (research; USBF records for bot evaluation)"; B=https://vugraph.lovebridge.com
M=usbc_397454_2_1
for ns in "OP%201" "CL%201" "1" "OP1"; do curl -sS -m 30 -A "$UA" "$B/api/archive/watch/$M/$ns/31" -o w.json -w "%{http_code} %{size_download} watch/$ns/31\n"; done
curl -sS -m 30 -A "$UA" "$B/api/archive/watch/$M/OP%201/31" -o w.json; python3 - <<'PY'
import json
e = json.load(open('w.json'))
print(type(e), len(e))
if e:
    import collections
    print(collections.Counter(x.get('tt') for x in e))
    for x in e[:3] + e[8:12] + e[-3:]: print(json.dumps(x)[:400])
PY
