# boxctl: timeout=900
# loop session (Max, 17:43 UTC: "Do we need a wider net?"): read-only. The pool-trained net (rollout net v2, 768 wide, 5 epochs
# on 30.4M rows) scored on a random 400,000 of the rows it was TRAINED on and on the held-out deals (freshB), bot by bot:
# the gap between the two is what more data could still close; no gap means the net, not the data, is the limit.
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python; D=$HOME/work/plan/rnet2w/data
cd "$S2"; export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
V2=models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz; ls -la "$V2" | cut -c1-120
nice -n 10 "$PY" training/rollout-loop-20261113/sample_set.py "$D/train.npz" /tmp/v2train.npz --rows 400000 --seed 7 | cut -c1-300
nice -n 10 "$PY" scripts/score_rollout_nets.py --data /tmp/v2train.npz --net v2="$V2" --out /tmp/score_v2train.json 2>&1 | grep -v Warning | tail -3 | cut -c1-200
nice -n 10 "$PY" scripts/score_rollout_nets.py --data "$D/freshB.npz" --net v2="$V2" --out /tmp/score_v2fresh.json 2>&1 | grep -v Warning | tail -3 | cut -c1-200
"$PY" - <<'PY'
import json
a = json.load(open('/tmp/score_v2train.json')); b = json.load(open('/tmp/score_v2fresh.json'))
print('keys:', list(a.keys())[:6], '|', list(a[list(a.keys())[0]].keys())[:12])
for name in a:
    x, y = a[name], b[name]
    def row(label, p, q):
        f = lambda s, k: ('%.4f' % s[k]) if s and s.get(k) is not None else '   -  '
        print('%-18s rows %7s / %6s | log-loss %s / %s | exact %s / %s | tricks given up %s / %s | gap head %s / %s' % (
            label, p.get('n') if p else '-', q.get('n') if q else '-', f(p, 'nll'), f(q, 'nll'), f(p, 'agree'), f(q, 'agree'), f(p, 'regret'), f(q, 'regret'), f(p, 'regret_gap_head'), f(q, 'regret_gap_head')))
    print('==', name, '(trained-on rows / held-out rows)')
    row('all', x.get('all'), y.get('all'))
    row('from trick 7', x.get('from_trick_7'), y.get('from_trick_7'))
    bots = sorted(set(x.get('by_bot', {})) | set(y.get('by_bot', {})), key=lambda k: -(x.get('by_bot', {}).get(k, {}).get('n', 0)))
    for bot in bots[:12]:
        row('bot ' + bot, x.get('by_bot', {}).get(bot), y.get('by_bot', {}).get(bot))
PY
rm -f /tmp/v2train.npz; date -u +%T
