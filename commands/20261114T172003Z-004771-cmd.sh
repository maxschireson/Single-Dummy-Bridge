# boxctl: timeout=120
# loop session: read-only look at one gate record's layout (for a check of the rollouts' values against the table's result).
set -euo pipefail
W=$HOME/work/loop
ls "$W/runs/bu3-pst200a-1" | head -8
D=$(ls -d "$W"/runs/bu3-pst200a-1/episodes* 2>/dev/null | head -1); echo "dir: $D"; ls "$D" | head -3; ls "$D" | wc -l
F=$(ls "$D"/*.json.gz | head -1)
python3 - "$F" <<'PY'
import gzip, json, sys
d = json.load(gzip.open(sys.argv[1], 'rt'))
print('top keys:', sorted(d.keys())[:30])
print('candidate', d.get('candidate'), 'opponent', d.get('opponent'))
ut = d['unique_tables']
print('unique_tables:', len(ut))
e = next(iter(ut.values()))
print('entry keys:', sorted(e.keys()))
print('board:', json.dumps(e['board'])[:400])
for t in e['tables']:
    print('table keys:', sorted(t.keys()), '| declarer_tricks', t.get('declarer_tricks'), '| actions', len(t['actions']), '| depth', t.get('depth'), t.get('fork_kind'))
    shown = 0
    for a in t['actions']:
        note = a.get('x8') or (a.get('details') or {}).get('x8')
        if note and note.get('mode') == 'rollout' and shown < 2:
            shown += 1
            print(' action keys:', sorted(a.keys()))
            print(' note:', json.dumps({k: (v if k != 'cap' else {kk: (vv if kk == 'shape' else str(vv)[:40]) for kk, vv in v.items()}) for k, v in note.items() if k != 'forks'})[:1200])
    kinds = {}
    for a in t['actions']:
        note = a.get('x8') or {}
        key = (a.get('player') or a.get('role'), note.get('mode'), note.get('claim'))
        kinds[key] = kinds.get(key, 0) + 1
    print(' actions by (player, mode, claim):', kinds)
PY
