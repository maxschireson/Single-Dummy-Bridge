# boxctl: timeout=1500
# boxctl: timeout=1500
# loop session: a smoke test of the new seat and blind settings on azure1, beside its match (2 workers at Nice 10, second
# checkout, results in /tmp): pure Stu's fingerprint tables on the new code (cards must be what they were: 98816ce14af8b825),
# then a few boards of the split-seat bot, the blind bot and the blind-split bot.
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python
[ -d "$S2/.git" ] || git clone -q --depth 5 --branch research/rollout-loop-20261113 https://github.com/maxschireson/Single-Dummy-Bridge "$S2"
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q b2937074b08f639de3a0e58ba8bd8f10502405c0
for d in bridge_harness/libbridge_dds.so models/cardplay; do [ -e "$S2/$d" ] && [ ! -L "$S2/$d" ] && rm -rf "$S2/$d"; ln -sfn "$W/src/$d" "$S2/$d"; done
cd "$S2"; export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
rm -rf /tmp/smoke; mkdir -p /tmp/smoke
run() { timeout 600 nice -n 10 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair "$2" --deals "$3" --first "$4" --seed "$5" --workers 2 --episodes $6 --out /tmp/smoke/$1 2>&1 | grep -v Warning | tail -1 | cut -c1-150; }
run pf-one stu0-pa~stu0-pb 8 0 9000 --one-room
run px stu3-px~stu0-ps 3 5000 131 ""
run pu stu3-pu~8p-32-v41 3 500 131 ""
run pux stu3-pux~8p-32-v41 3 500 131 ""
"$PY" - <<'PY'
import glob, gzip, json, hashlib
for run in ('pf-one', 'px', 'pu', 'pux'):
    rows = [json.loads(l) for l in open(f'/tmp/smoke/{run}/results.jsonl')]
    cards = hashlib.sha256(); notes = []
    for f in sorted(glob.glob(f'/tmp/smoke/{run}/episodes/*')):
        d = json.load(gzip.open(f, 'rt'))
        for e in d['unique_tables'].values():
            for t in e['tables']:
                cards.update(' '.join(a['card'] for a in t['actions']).encode())
                notes += [a['x8'] for a in t['actions'] if (a.get('x8') or {}).get('mode') == 'rollout' and a.get('player') == d['candidate']]
    print(run, 'boards', len(rows), 'cpu a board %.1f' % (sum(r['cpu'] for r in rows) / len(rows)), 'IMPs', [r.get('common') for r in rows][:4],
          'cards digest', cards.hexdigest()[:16], '| rollout decisions of the first bot', len(notes), 'mean candidates %.2f' % (sum(len(n['cards']) for n in notes) / max(1, len(notes))))
m = json.load(open('/tmp/smoke/pux/manifest.json'))['bots']['stu3-pux']
print('pux pinned:', {k: m['x8']['stages'][0].get(k) for k in ('seat', 'cut', 'seat_other', 'cut_other')}, 'blind', m['x8'].get('blind'), 'names', m['x8']['names'], 'mix', {k: m['x8']['mix'][k] for k in ('declarer', 'defender', 'read_declarer', 'read_defender')})
m = json.load(open('/tmp/smoke/pf-one/manifest.json'))['bots']['stu0-pa']
print('stu0-pa pinned stage keys:', sorted(m['x8']['stages'][0]))
PY
date -u +%FT%TZ
