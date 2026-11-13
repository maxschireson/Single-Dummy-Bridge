# boxctl: timeout=1500
# boxctl: timeout=1500
# loop session: pure minus Stu is +0.08 on deals 0-499 (azure3) and -0.74 on deals 500-999 (azure5). A match is
# deterministic given its seed, so replay azure3's first 64 deals of l0-p here and compare board by board: if they agree,
# the two halves differ by the deals; if not, the boxes differ. Waits for l0b-p to finish, holds the collection for it.
set -euo pipefail
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113; PY=$W/venv/bin/python
for i in $(seq 1 40); do [ "$(wc -l < "$W/runs/l0b-p/results.jsonl")" -ge 500 ] && break; sleep 15; done
echo "l0b-p at $(wc -l < "$W/runs/l0b-p/results.jsonl") boards"; tail -n 2 "$W/runs.log" | cut -c1-140
sudo systemctl stop loop-collect || true
sudo systemctl stop plan-queue plan-publish 2>/dev/null || true      # plan, 10:56 UTC on the board: "can be stopped whenever you like"
cd "$S"
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
rm -rf "$W/runs/x0-p"; t0=$(date +%s)
timeout 1100 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair stu0-p~8p-32-v41 --deals 64 --first 0 --seed 131 --workers 8 --episodes --out "$W/runs/x0-p" 2>&1 | tail -1 | cut -c1-200
echo "x0-p: $(( $(date +%s) - t0 )) s wall"
rm -rf /tmp/a3rows; git clone -q --depth 1 --branch transfer/rollout-loop-azure3-20261113 https://github.com/maxschireson/Single-Dummy-Bridge /tmp/a3rows 2>&1 | tail -1
"$PY" - <<'PY'
import json, os
W = os.path.expanduser('~/work/loop/runs')
here = {r['index']: r for r in map(json.loads, open(f'{W}/x0-p/results.jsonl'))}
there = {r['index']: r for r in map(json.loads, open('/tmp/a3rows/l0-p/results.jsonl'))}
both = sorted(set(here) & set(there))
same = [i for i in both if here[i]['common'] == there[i]['common']]
key = lambda r: tuple((r['search'][role].get('x8') or {}).get(k) for role in ('candidate', 'opponent') for k in ('rollout', 'claim', 'moved', 'guaranteed', 'rollouts', 'asked'))
exact = [i for i in both if key(here[i]) == key(there[i])]
print('boards compared', len(both), '| same IMPs', len(same), '| same decision counts (rollouts, claims, moved, claim questions)', len(exact))
print('mean here %+.3f there %+.3f' % (sum(here[i]['common'] for i in both) / len(both), sum(there[i]['common'] for i in both) / len(both)))
diff = [(i, here[i]['common'], there[i]['common']) for i in both if i not in same]
print('boards that differ (index, here, azure3):', diff[:20])
print('cpu a board here %.1f there %.1f' % (sum(here[i]['cpu'] for i in both) / len(both), sum(there[i]['cpu'] for i in both) / len(both)))
for name, rows in (('here', here), ('azure3', there)):
    c = [rows[i]['search']['candidate'].get('x8') or {} for i in both]
    print(name, 'candidate totals:', {k: round(sum(x.get(k, 0) for x in c), 1) for k in ('rollout', 'claim', 'moved', 'guaranteed', 'guarantee_moved', 'odds', 'rollouts', 'net_rows', 'asked', 'ended', 'floored')})
PY
git -C "$S" log -1 --format='source %h' ; sha256sum "$W/bin/sure_cpp" "$S/models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz" | cut -c1-20,65-
sudo systemctl reset-failed loop-collect 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure5.txt"
sleep 30; systemctl is-active loop-collect loop-publish | tr '\n' ' '; echo; tail -n 2 "$W/runs.log" | cut -c1-150; date -u +%FT%TZ
