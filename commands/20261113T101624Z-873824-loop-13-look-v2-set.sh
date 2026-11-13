# boxctl: timeout=900
# loop session: read-only look at azure5 before round 1's set: the collection's count, and the plan session's warm-run
# set (file names, sizes, row counts, bots), which round 1 would draw the other bots' rows from. Nothing is changed.
W=$HOME/work/loop; D=$HOME/work/plan/rnet2w/data
echo "s0: $(wc -l < "$W/runs/s0/results.jsonl") boards; $(tail -n 1 "$W/runs/s0.log" | cut -c1-110)"
ls -la "$D" | cut -c1-140
"$W/venv/bin/python" - <<'PY'
import os, zipfile, numpy as np
D = os.path.expanduser('~/work/plan/rnet2w/data')
for name in sorted(os.listdir(D)):
    if not name.endswith('.npz'):
        continue
    p = os.path.join(D, name)
    with zipfile.ZipFile(p) as z:
        stored = all(m.compress_type == zipfile.ZIP_STORED for m in z.infolist())
        names = [m.filename for m in z.infolist()]
    z = np.load(p, mmap_mode='r')
    meta = z['meta']; bots = [str(x) for x in z['bot_names']]
    print(name, '| rows', len(meta), '| deals', len(z['family']), '| stored uncompressed', stored, '| arrays', sorted(n[:-4] for n in names))
    by = np.bincount(np.asarray(meta[:, 8]), minlength=len(bots))
    print('   rows by deciding bot:', {b: int(n) for b, n in zip(bots, by) if n})
    print('   has_gap share', round(float(np.asarray(meta[:, 10]).mean()), 3), '| meta columns', [str(x) for x in z['meta_columns']])
PY
ls "$HOME/work/plan/rnet2w/warm" 2>/dev/null | head -8 | tr '\n' ' '; echo; free -g | sed -n 2p; df -h ~ | tail -1; uptime
