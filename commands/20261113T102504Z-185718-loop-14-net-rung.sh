# boxctl: timeout=1500
# boxctl: timeout=1500
# loop session: add each net alone to the ladder (the dashboard session's ask for Max, board 09:58 UTC). Check out the
# commit with the two bots and the engine hook that tells a net playing alone who it is; test them on four boards (and
# that the names reach the net: the same boards with the names blank must differ somewhere); restart the chain from the
# new job file. Rungs already played are kept; the rung in hand replays at most the boards it had in flight.
set -euo pipefail
COMMIT=e57865fc904de3e82cd12c2aa229b05cc2cd5ac5
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113; PY=$W/venv/bin/python
sudo systemctl stop loop-chain || true
tail -n 2 "$W/runs.log" | cut -c1-140
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-110
cd "$S"
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
"$PY" - <<'PY'
import copy, json, os
d = json.load(open('configs/loop-bots.json'))
b = copy.deepcopy(d); b['stu0-n']['x8'].pop('names')
json.dump(b, open(os.path.expanduser('~/work/loop/blank-bots.json'), 'w'))
PY
for t in "pf-n configs/loop-bots.json stu0-n" "pf-nb $W/blank-bots.json stu0-n" "pf-v1n configs/loop-bots.json stu0v1-n"; do
  set -- $t; rm -rf "$W/runs/$1"
  timeout 600 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots "$2" --pair "$3~8p-32-v41" --deals 4 --first 0 --seed 9000 --workers 4 --episodes --out "$W/runs/$1" 2>&1 | tail -1 | cut -c1-130
done
"$PY" - <<'PY'
import collections, glob, gzip, json, os
W = os.path.expanduser('~/work/loop/runs')
def cards(run):
    out, modes = {}, collections.Counter()
    for f in sorted(glob.glob(f'{W}/{run}/episodes/*')):
        d = json.load(gzip.open(f, 'rt'))
        for tk, e in d['unique_tables'].items():
            for a in e['tables'][0]['actions']:
                if a['player'] == 'candidate' and len(a.get('behavior_probabilities') or {}) > 1:
                    out[(d['index'], tk, a['ply'])] = a['card']
                    modes[(a.get('x8') or {}).get('mode') or ('search' if a.get('estimates') else 'net')] += 1
    return out, modes
a, ma = cards('pf-n'); b, mb = cards('pf-nb'); c, mc = cards('pf-v1n')
same = [k for k in a if k in b]
print('stu0-n decisions by method', dict(ma), '| stu0v1-n', dict(mc))
print('v2 alone, told 8s-32 against no name: positions reached by both', len(same), 'of', len(a), '| different card at', sum(a[k] != b[k] for k in same))
ok = set(ma) == {'net'} and set(mc) == {'net'} and (len(same) < len(a) or any(a[k] != b[k] for k in same))
print('NET RUNG', 'OK' if ok else 'CHECK FAILED')
PY
rm -rf "$W/runs/pf-n" "$W/runs/pf-nb" "$W/runs/pf-v1n" "$W/blank-bots.json"
sudo systemctl reset-failed loop-chain 2>/dev/null || true
sudo systemd-run --unit=loop-chain --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$T/chain.sh" "$T/jobs-azure3.txt"
sleep 40; systemctl is-active loop-chain loop-publish | tr '\n' ' '; echo; tail -n 3 "$W/runs.log" | cut -c1-150; date -u +%FT%TZ
