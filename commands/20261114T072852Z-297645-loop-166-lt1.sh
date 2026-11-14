# boxctl: timeout=900
# boxctl: timeout=900
# loop session (read-only toward the records; Nice 15, 2 workers): lost_tricks.py on the two sessions already harvested, timed.
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q ead62af1f3f12ec8b9402770ca49117870cdb34c
for d in bridge_harness/libbridge_dds.so; do [ -e "$S2/$d" ] && [ ! -L "$S2/$d" ] && rm -rf "$S2/$d"; ln -sfn "$W/src/$d" "$S2/$d"; done
cd "$S2"; export BRIDGE_DDS_CACHE=
rm -f /tmp/lt.jsonl.gz
time nice -n 15 "$PY" training/rollout-loop-20261113/usbc/lost_tricks.py $HOME/work/usbc/records /tmp/lt.jsonl.gz --workers 2
"$PY" - <<'PY'
import gzip, json, collections
rows = [json.loads(l) for l in gzip.open('/tmp/lt.jsonl.gz', 'rt') if not l.startswith('{"file"')]
err = [r for r in rows if 'error' in r]; ok = [r for r in rows if 'error' not in r]
print('tables', len(rows), 'errors', len(err), collections.Counter(r['error'][:40] for r in err).most_common(3))
deals = collections.Counter(r['deal'] for r in ok); print('distinct deals', len(deals), 'tables a deal', collections.Counter(deals.values()).most_common(5))
L = collections.defaultdict(float); n = collections.Counter()
for r in ok:
    for d in r['decisions']:
        L[d[2]] += d[3]; n[d[2]] += 1
print('per table: ' + ', '.join(f'{k} {L[k] / len(ok):.3f} ({n[k]} decisions)' for k in sorted(L)))
print('claims', sum('claim' in r for r in ok), 'scored claims with a difference', sum(1 for r in ok for d in r['decisions'] if d[2] in ('CD', 'CF')))
print(json.dumps(ok[0])[:600])
PY
