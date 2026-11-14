# boxctl: timeout=600
# boxctl: timeout=600
# loop session (Max, 06:59 UTC: the Azure boxes fetch the USBC records): harvest.py on two sessions first (a check of the
# format), from the second checkout, at a quarter second a request.
set -uo pipefail
W=$HOME/work/loop; S2=$W/src-lc
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q 0c8afbad8ec1c420f5a231731e83bcdf514ba669
timeout 560 python3 "$S2/training/rollout-loop-20261113/usbc/harvest.py" $HOME/work/usbc/records --limit 2 2>&1 | tail -8
python3 - <<'PY'
import gzip, json, glob, os
for f in sorted(glob.glob(os.path.expanduser('~/work/usbc/records/*.json.gz')))[:2]:
    d = json.load(gzip.open(f, 'rt'))
    t = d['tables'][0] if d['tables'] else None
    print(os.path.basename(f), d['meta'].get('namePlus'), 'boards', len(d['boards']), 'matches', len(d['matches']), 'tables', len(d['tables']))
    if t:
        full = t['events'][0]['payload']; print('  e.g. board', t['board'], 'room', full.get('room'), 'auction', [b['bv'] for b in full.get('bg', [])], 'result', full.get('orRes', {}).get('cdto'))
PY
python3 -c "import json; d=json.load(open('$HOME/work/usbc/records/index.json')); print(len(d))" 2>/dev/null
