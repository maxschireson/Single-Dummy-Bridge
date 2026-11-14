# boxctl: timeout=180
# boxctl: timeout=180
# loop session (read-only): the USBF mini-sessions in LoveBridge vugraph's archive list, and one match's boards.
set -uo pipefail
D=$HOME/work/usbc/probe; cd $D
UA="Mozilla/5.0 (research; USBF records for bot evaluation)"; B=https://vugraph.lovebridge.com
python3 - <<'PY'
import json, collections
ms = json.load(open('ms.json'))
print('mini-sessions', len(ms), '| keys', sorted(ms[0])[:40])
u = [m for m in ms if 'usb' in m['miniSessionId'].lower() or 'usbc' in (m.get('namePlus') or '').lower() or 'usbf' in str(m.get('clubId'))]
print('USBF-looking', len(u))
by = collections.Counter((m['miniSessionId'].split('_')[0], m['startDateTime'][:7]) for m in u)
for k, v in sorted(by.items()): print(' ', k, v)
for m in u[:6] + [x for x in u if '631412' in x['miniSessionId']][:3]:
    print(m['miniSessionId'], '|', m.get('name'), '|', m.get('namePlus'), '|', m['startDateTime'][:10], m.get('type'), m.get('calcType'), m.get('boardsPerRound'), m.get('eventId'))
json.dump(u, open('usbf_ms.json', 'w'))
PY
id=$(python3 -c "import json; u=json.load(open('usbf_ms.json')); x=[m for m in u if '631412' in m['miniSessionId']] or u; print(x[0]['miniSessionId'])")
echo "probe $id"
curl -sS -m 30 -A "$UA" "$B/api/archive/boards/$id" -o b.json -w "%{http_code} %{size_download}\n"; head -c 900 b.json; echo
curl -sS -m 30 -A "$UA" "$B/api/archive/board/$id/1" -o b1.json -w "%{http_code} %{size_download}\n"; head -c 2500 b1.json; echo
