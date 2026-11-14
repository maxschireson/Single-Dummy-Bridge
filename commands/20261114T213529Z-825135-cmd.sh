# boxctl: timeout=1500
# loop session: H01 (#37, owner loop): a read-only inventory of this box's Stu episode folders (files, bytes, sha256 of each file,
# rollout decisions, inside-rollout pairs) to pub/h01/inventory-azure2.json for the publisher. Nice 19; nothing else is touched.
set -uo pipefail
W=$HOME/work/loop; PY=$W/venv/bin/python
mkdir -p "$W/pub/h01"
nice -n 19 "$PY" - "$W" <<'PY'
import gzip, json, hashlib, glob, os, sys, time
W = sys.argv[1]
out = dict(box='azure2', made=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), runs={})
for d in sorted(glob.glob(W + '/runs/*/episodes')):
    run = d.split('/')[-2]
    files = sorted(glob.glob(d + '/*.json.gz'))
    if not files: continue
    try: m = json.load(open(os.path.dirname(d) + '/manifest.json'))
    except Exception: m = {}
    roster = m.get('roster') or []
    if not any(str(r).startswith('stu') for r in roster): continue          # Stu's records only
    rec = dict(roster=roster, seed=m.get('seed'), files=len(files), bytes=0, with_pairs=0, pairs=0, rollout_decisions=0, failed=[], sha256={})
    for f in files:
        b = open(f, 'rb').read(); rec['bytes'] += len(b); rec['sha256'][os.path.basename(f)] = hashlib.sha256(b).hexdigest()
        try:
            e = json.loads(gzip.decompress(b))
            n = k = 0
            for t in e['unique_tables'].values():
                for table in t.get('tables') or ():
                    if table.get('depth', 0) or table.get('fork_kind'): continue
                    for a in table['actions']:
                        note = a.get('x8') or {}
                        if note.get('mode') == 'rollout':
                            k += 1; n += len(note.get('forks') or ())
            rec['pairs'] += n; rec['rollout_decisions'] += k; rec['with_pairs'] += n > 0
        except Exception as ex:
            rec['failed'].append([os.path.basename(f), str(ex)[:80]])
    out['runs'][run] = rec
    print('%-8s %6d files %7.1f MB | rollout decisions %8d | pairs %9d | records with pairs %6d | failed %d' % (run, rec['files'], rec['bytes'] / 1e6, rec['rollout_decisions'], rec['pairs'], rec['with_pairs'], len(rec['failed'])))
json.dump(out, open(W + '/pub/h01/inventory-azure2.json', 'w'))
print('totals: files', sum(r['files'] for r in out['runs'].values()), '| pairs', sum(r['pairs'] for r in out['runs'].values()), '| rollout decisions', sum(r['rollout_decisions'] for r in out['runs'].values()))
PY
date -u +%T
