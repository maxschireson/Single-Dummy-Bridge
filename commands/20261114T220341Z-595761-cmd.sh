# boxctl: timeout=90
W=$HOME/work/loop; wc -l $W/pub/h05/*.jsonl; systemctl is-active loop-pairs
cat $W/pub/h05/report-both.txt 2>/dev/null | tail -17
$W/venv/bin/python - $W/pub/h05/pairs-sp3s.jsonl $W/pub/h05/pairs-sp0.jsonl <<'PY'
import json, sys, numpy as np
rows = [json.loads(l) for f in sys.argv[1:] for l in open(f) if l.strip()]
rows = [r for r in rows if 'single' in r]
print('CPU a pair and share of pairs, by trick of the fork; and share whose panel differs from 0 by over 2 SE and by over 0.25 trick')
for lo, hi in ((1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 13)):
    s = [r for r in rows if lo <= r['trick'] <= hi]
    q = np.array([r['panel'] for r in s]); se = np.array([r['se'] for r in s])
    print(f'tricks {lo}-{hi}: share {len(s)/len(rows):.3f}  cpu {np.mean([r["cpu"] for r in s]):.2f} s  layouts {np.mean([r["layouts"] for r in s]):.0f}  |panel|>2SE {np.mean(np.abs(q)>2*se):.2f}  |panel|>0.25 {np.mean(np.abs(q)>0.25):.2f}')
PY
