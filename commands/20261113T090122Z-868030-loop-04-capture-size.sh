# boxctl: timeout=2400
# boxctl: timeout=2400
# loop session (Max, 08:59 UTC: "See how much bigger / if it matters"): the size and cost of per-layout recording.
# The round-0 bot plays the same six deals twice, three workers at Nice 5 beside the gate match: as the collection
# records them (capture level 1), and with every layout's result for every candidate kept (level 2, up to 128 layouts).
# The 64-layout size is computed from the 128-layout records. Then: are the cards the same, and can each candidate's
# mean be rebuilt from the per-layout results.
set -euo pipefail
W=$HOME/work/loop; S=$W/src; PY=$W/venv/bin/python; cd "$S"
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
"$PY" - <<'PY'
import copy, json, os
W = os.path.expanduser('~/work/loop')
d = json.load(open('configs/loop-bots.json'))
json.dump(d, open(f'{W}/cap1-bots.json', 'w'))
b = copy.deepcopy(d)
for k in ('z0a-v2', 'z0b-v2'):
    b[k]['x8']['capture'].update(level=2, layouts=128)
json.dump(b, open(f'{W}/cap2-bots.json', 'w'))
PY
for tag in cap1 cap2; do
  rm -rf "$W/runs/t-$tag"; t0=$(date +%s)
  timeout 900 nice -n 5 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots "$W/$tag-bots.json" --pair z0a-v2~z0b-v2 --deals 6 --first 0 --seed 9000 --workers 3 --episodes --out "$W/runs/t-$tag" 2>&1 | tail -1 | cut -c1-260
  echo "$tag: $(( $(date +%s) - t0 )) s wall"
done
"$PY" - <<'PY'
import base64, glob, gzip, io, json, os
import numpy as np
W = os.path.expanduser('~/work/loop/runs')
def load(tag):
    return {os.path.basename(f): json.load(gzip.open(f, 'rt')) for f in sorted(glob.glob(f'{W}/t-{tag}/episodes/*'))}
def notes(x, contract=None, out=None):
    out = [] if out is None else out
    if isinstance(x, dict):
        b = x.get('board')
        if isinstance(b, dict) and b.get('contract'):
            contract = b['contract']
        n = x.get('x8')
        if isinstance(n, dict) and 'mode' in n:
            out.append((contract, n))
        for v in x.values():
            notes(v, contract, out)
    elif isinstance(x, list):
        for v in x:
            notes(v, contract, out)
    return out
def gz(obj):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb', mtime=0) as f:
        f.write(json.dumps(obj, separators=(',', ':')).encode())
    return len(buf.getvalue())
def unpack(text, dtype, shape=None):
    a = np.frombuffer(base64.b64decode(text), dtype)
    return a if shape is None else a.reshape(shape)
def pack(a, dtype):
    return base64.b64encode(np.ascontiguousarray(a, dtype).tobytes()).decode()
one, two = load('cap1'), load('cap2')
size = lambda tag: {os.path.basename(f): os.path.getsize(f) for f in glob.glob(f'{W}/t-{tag}/episodes/*')}
s1, s2 = size('cap1'), size('cap2')
print('boards', len(one), len(two))
print('bytes a board as written: level 1', sum(s1.values()) // len(s1), '| level 2, 128 layouts', sum(s2.values()) // len(s2))
print('bytes a board re-encoded the same way: level 1', sum(gz(v) for v in one.values()) // len(one), '| level 2, 128 layouts', sum(gz(v) for v in two.values()) // len(two))
# the 64-layout size: keep each block's first 64 layouts (blocks are sorted by weight, heaviest first, as capture_block does)
cut = json.loads(json.dumps(two)); full = part = 0
for c, n in notes(cut):
    cap = n.get('cap')
    if not cap:
        continue
    k, m = cap['shape']
    if k > 64:
        t = unpack(cap['t'], np.int8, (k, m)); f = unpack(cap['f'], np.uint8, (k, m)); w = unpack(cap['w'], np.float32)
        cap.update(layouts=cap['layouts'][:64], w=pack(w[:64], np.float32), t=pack(t[:64], np.int8), f=pack(f[:64], np.uint8), shape=[64, m]); part += 1
    else:
        full += 1
print('| level 2, 64 layouts', sum(gz(v) for v in cut.values()) // len(cut), f'(decisions with a block: {full + part}, of them over 64 layouts: {part})')
# same cards?
c1 = [(c, n.get('mode'), n.get('trick'), n.get('chosen')) for v in one.values() for c, n in notes(v)]
c2 = [(c, n.get('mode'), n.get('trick'), n.get('chosen')) for v in two.values() for c, n in notes(v)]
print('decision notes', len(c1), len(c2), '| same modes, tricks and cards in the same order:', c1 == c2)
r1 = [json.loads(l) for l in open(f'{W}/t-cap1/results.jsonl')]; r2 = [json.loads(l) for l in open(f'{W}/t-cap2/results.jsonl')]
key = lambda r: (r['index'], r.get('contract'), r.get('common'))
print('same contracts and results:', sorted(map(key, r1)) == sorted(map(key, r2)), '| cpu a board', round(sum(r['cpu'] for r in r1) / len(r1), 1), round(sum(r['cpu'] for r in r2) / len(r2), 1))
# can each candidate's mean be rebuilt from the per-layout results?
by = {}; worst = 0.; checked = 0; modes = {}
for c, n in (x for v in two.values() for x in notes(v)):
    modes[n['mode']] = modes.get(n['mode'], 0) + (1 if n.get('cap') else 0)
    cap = n.get('cap')
    if n['mode'] != 'rollout' or not cap or not n.get('roll') or len(n['cards']) < 2:
        continue
    k, m = cap['shape']
    t = unpack(cap['t'], np.int8, (k, m)).astype(float); f = unpack(cap['f'], np.uint8, (k, m)).astype(bool); w = unpack(cap['w'], np.float32).astype(float)
    target = int(c[0]) + 6
    final = np.where(f & (t >= 0), np.maximum(t, target), t)
    played = t >= 0
    for j in range(m):
        if n['roll'][j] is None or not played[:, j].any() or k < n['layouts']:
            continue
        mean = float(w[played[:, j]] @ final[played[:, j], j] / w[played[:, j]].sum())
        worst = max(worst, abs(abs(mean) - abs(n['roll'][j]))); checked += 1
    by.setdefault(min(k, 128), 0); by[min(k, 128)] += 1
print('blocks by mode', modes)
print('candidates whose mean tricks were rebuilt from the per-layout results:', checked, '| largest difference from the recorded mean:', round(worst, 4))
ks = sorted(by); print('rollout decisions by layouts kept:', {k: by[k] for k in ks[:3]}, '...', {k: by[k] for k in ks[-3:]})
PY
rm -rf "$W/runs/t-cap1" "$W/runs/t-cap2"; tail -n 1 "$W/runs/g0-v2.log" | cut -c1-160; date -u +%FT%TZ
