# boxctl: timeout=2400
# boxctl: timeout=2400
# loop session (Max, 11:29 UTC: rollouts for the opening lead, every lead on 512 layouts): check out the engine change,
# test the rolled-lead bot on a few boards (against Gen 8 card play and against itself), build rows from its records.
# The chain is stopped for the test and restarted on the same job file (the run in hand resumes).
set -euo pipefail
COMMIT=0a87e0156d68f46e9f8da2c7be0ca81611e3559a
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113; PY=$W/venv/bin/python
sudo systemctl stop loop-chain || true
tail -n 1 "$W/runs.log" | cut -c1-140; echo "l0-p at $(wc -l < "$W/runs/l0-p/results.jsonl") boards"
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-110
cd "$S"
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
for t in "pf-pr stu0-pr~8p-32-v41 8" "pf-prr stu0-pra~stu0-prb 8"; do
  set -- $t; rm -rf "$W/runs/$1"; t0=$(date +%s)
  timeout 1500 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair "$2" --deals "$3" --first 0 --seed 9000 --workers 8 --episodes --out "$W/runs/$1" 2>&1 | tail -1 | cut -c1-150
  echo "$1: $(( $(date +%s) - t0 )) s wall"
done
"$PY" - <<'PY'
import collections, glob, gzip, json, os, sys
W = os.path.expanduser('~/work/loop/runs'); ok = True
for run, roles in (('pf-pr', ('candidate',)), ('pf-prr', ('candidate', 'opponent'))):
    files = sorted(glob.glob(f'{W}/{run}/episodes/*'))
    leads, later, secs, rows_, cands, moved, capk, bad = collections.Counter(), collections.Counter(), [], [], [], 0, [], 0
    for f in files:
        d = json.load(gzip.open(f, 'rt'))
        for e in d['unique_tables'].values():
            for a in e['tables'][0]['actions']:
                if a['player'] in roles and len(a.get('behavior_probabilities') or {}) > 1:
                    n = a.get('x8') or {}
                    mode = n.get('mode') or ('search' if a.get('estimates') else 'net')
                    if a['ply'] == 0:
                        leads[mode + ('+lead' if n.get('lead') else '')] += 1
                        if n.get('lead'):
                            secs.append(n.get('seconds') or {}); rows_.append(n.get('net_rows', 0)); cands.append(len(n['cards']))
                            moved += n['chosen'] not in n['runs'][0]
                            capk.append((n['cap']['shape'][0], n['layouts'], len(n['cap']['layouts'])))
                            bad += set(n['n']) != {n['layouts']} or len(n['alive']) != len(n['cards']) or sorted(x for r in n['runs'] for x in r) != sorted(a['behavior_probabilities'])
                    else:
                        later[mode] += 1
    rows = [json.loads(l) for l in open(f'{W}/{run}/results.jsonl')]
    k = max(len(secs), 1)
    print(run, '| leads', dict(leads), '| later', dict(later))
    print('   lead rollouts: candidates %.1f (min %d max %d) | layouts kept/played %s | moved off the net\'s lead %d of %d | seconds a lead: layouts %.2f rollouts %.2f | net rows a lead %d | malformed %d'
          % (sum(cands) / k, min(cands or [0]), max(cands or [0]), sorted(set(capk))[:3], moved, len(secs), sum(s.get('layouts', 0) for s in secs) / k, sum(s.get('rollouts', 0) for s in secs) / k, sum(rows_) / k, bad))
    print('   bytes a board', sum(map(os.path.getsize, files)) // max(len(files), 1), '| cpu a board', round(sum(r['cpu'] for r in rows) / max(len(rows), 1), 1),
          '| x8 summary keys with lead:', sorted(k for k in rows[0]['search']['candidate'].get('x8', {}) if k.startswith('lead')), '| IMPs', [r['common'] for r in rows])
    ok &= len(rows) > 0 and bad == 0 and len(secs) > 0 and set(leads) <= {'rollout+lead'} and 'search' not in later
print('LEAD ROLLOUT BOTS', 'OK' if ok else 'CHECK FAILED')
PY
R=$W/pf-rows; rm -rf "$R"; mkdir -p "$R/eps"; ln "$W"/runs/pf-prr/episodes/* "$R/eps/"
SCORER=models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz
"$PY" scripts/gen7_build_dataset.py --episodes "$R/eps" --scorer "$SCORER" --out "$R/rows.npz" --workers 4 --policy-only --rollout-gap --alias "stu0-pra=stu0,stu0-prb=stu0" 2>&1 | tail -1 | cut -c1-200
"$PY" - <<'PY'
import numpy as np, os
d = np.load(os.path.expanduser('~/work/loop/pf-rows/rows.npz'), allow_pickle=True)
cols = [str(c) for c in d['meta_columns']]; meta = d['meta']; ply = meta[:, cols.index('ply')]; has = meta[:, -1]
gap, legal = d['gap'].astype(np.float32), d['legal'].astype(bool)
lead = ply == 0
print('rows', len(ply), '| lead rows', int(lead.sum()), '| lead rows with a gap for every legal card', int(((np.where(legal, gap, 0) >= 0).all(axis=1) & lead & (has == 1)).sum()),
      '| mean legal cards at the lead %.1f' % legal[lead].sum(axis=1).mean(), '| mean gap of the cards not best at the lead %.3f tricks' % np.mean([g[l & (g > 0)].mean() for g, l in zip(gap[lead], legal[lead]) if (l & (g > 0)).any()]),
      '| share of lead cards within 0.05 of the best %.2f' % np.mean([(g[l] <= .05).mean() for g, l in zip(gap[lead], legal[lead])]))
PY
rm -rf "$W/runs/pf-pr" "$W/runs/pf-prr" "$R"
sudo systemctl reset-failed loop-chain 2>/dev/null || true
sudo systemd-run --unit=loop-chain --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure3.txt"
sleep 30; systemctl is-active loop-chain loop-publish | tr '\n' ' '; echo; tail -n 2 "$W/runs.log" | cut -c1-150; date -u +%FT%TZ
