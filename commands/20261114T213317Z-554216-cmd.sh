# boxctl: timeout=1200
# loop session (Max, 21:32 UTC: the inside-rollout data; #44's and perf's requests): (1) a unit (loop-widthpub) publishes the width
# run's log, metrics, each epoch's weights and the unit's peak memory under pub/exp-width/w1536/ every 5 minutes; (2) the width
# runs' held-out rows (freshB.npz) and the 400,000 trained-on rows of v2's train/held-out check (sample_set.py seed 7, rebuilt)
# go to pub/exp-width/ compressed with sha256; (3) H01: a read-only inventory of this box's Stu episode folders (files, bytes,
# sha256 of each file, records with inside-rollout pairs and the pairs' count) to pub/h01/inventory-azure5.json. Nice 19.
set -uo pipefail
W=$HOME/work/loop; PY=$W/venv/bin/python; D=$HOME/work/plan/rnet2w/data; S2=$W/src-lc
cat > "$W/widthpub.sh" <<'EOS'
#!/usr/bin/env bash
# loop: the width runs' logs, metrics and each epoch's weights (once each) into pub/exp-width/<run>/ every 5 minutes, with the
# training unit's peak memory and CPU, for the P10 report (perf) and the dashboard (#44). The publisher pushes pub/.
W=$HOME/work/loop; UNIT=$1; shift
while :; do
  for run in "$@"; do
    O=$W/pub/exp-width/$run; mkdir -p "$O"
    [ -f "$W/exp-width/$run.log" ] && grep -v -e '^epoch [0-9]* step' -e Warning "$W/exp-width/$run.log" > "$O/train.log"
    for f in "$W/exp-width/$run"/policy_epoch*.npz "$W/exp-width/$run/metrics.json" "$W/exp-width/$run/policy.npz"; do
      [ -f "$f" ] || continue; b=$(basename "$f"); [ -f "$O/$b" ] && [ "$b" != metrics.json ] && continue
      sleep 20; cp -f "$f" "$O/$b"; sha256sum "$O/$b" | cut -c1-64 > "$O/$b.sha256"     # an epoch file, after it is written
    done
    systemctl show "$UNIT" -p ActiveState -p MemoryPeak -p MemoryCurrent -p CPUUsageNSec -p ExecMainStartTimestamp > "$O/unit.txt" 2>/dev/null
    nproc >> "$O/unit.txt"
  done
  sleep 300
done
EOS
sudo systemctl stop loop-widthpub 2>/dev/null; sudo systemctl reset-failed loop-widthpub 2>/dev/null
sudo systemd-run --unit=loop-widthpub --uid="$USER" --working-directory="$W" --setenv=HOME="$HOME" -- bash "$W/widthpub.sh" loop-width w1536
mkdir -p "$W/pub/exp-width" "$W/pub/h01"
cd "$S2"
nice -n 19 "$PY" - "$D" "$W/pub/exp-width" <<'PY'
import numpy as np, sys, hashlib, os
D, O = sys.argv[1:3]
z = np.load(D + '/freshB.npz', allow_pickle=True)
np.savez_compressed(O + '/freshB.npz', **{k: z[k] for k in z.files})
for f in ('freshB.npz',):
    h = hashlib.sha256(open(O + '/' + f, 'rb').read()).hexdigest(); open(O + '/' + f + '.sha256', 'w').write(h + '\n')
print('freshB:', len(z['deal']), 'rows', os.path.getsize(O + '/freshB.npz') // 1024, 'KB compressed; the uncompressed original on the boxes has sha256 511d1d8c...')
PY
nice -n 19 "$PY" training/rollout-loop-20261113/sample_set.py "$D/train.npz" /tmp/v2train.npz --rows 400000 --seed 7 | cut -c1-120
nice -n 19 "$PY" -c "
import numpy as np, hashlib
z = np.load('/tmp/v2train.npz', allow_pickle=True)
np.savez_compressed('$W/pub/exp-width/v2_trained_rows_seed7.npz', **{k: z[k] for k in z.files})
h = hashlib.sha256(open('$W/pub/exp-width/v2_trained_rows_seed7.npz', 'rb').read()).hexdigest(); open('$W/pub/exp-width/v2_trained_rows_seed7.npz.sha256', 'w').write(h + '\n')
print('trained-on sample:', len(z['deal']), 'rows')
"; rm -f /tmp/v2train.npz
ls -la "$W/pub/exp-width" | tail -n 6 | cut -c1-110
nice -n 19 "$PY" - "$W" <<'PY'
import gzip, json, hashlib, glob, os, sys, time
W = sys.argv[1]
out = dict(box='azure5', made=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), runs={})
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
json.dump(out, open(W + '/pub/h01/inventory-azure5.json', 'w'))
print('totals: files', sum(r['files'] for r in out['runs'].values()), '| pairs', sum(r['pairs'] for r in out['runs'].values()), '| rollout decisions', sum(r['rollout_decisions'] for r in out['runs'].values()))
PY
date -u +%T
