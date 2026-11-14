# boxctl: timeout=60
# boxctl: timeout=60
# loop session (read-only): the shape of one table's events.
set -uo pipefail
cd $HOME/work/usbc/probe
python3 - <<'PY'
import json, collections
e = json.load(open('w_400345.json'))
print(type(e).__name__, len(e)); print(collections.Counter(x.get('tt') for x in e))
for x in e[:4]: print(json.dumps(x)[:700])
print('...')
for x in e[4:]:
    s = json.dumps(x)
    if any(k in s for k in ('"BID', 'CARD', 'PLAY', 'LEAD', 'CLAIM', 'RESULT', 'END')): print(s[:300])
PY
