# loop session: round 1's net is the one with only Stu's two vectors trained (vec-1e2): it learns most of what the whole
# net learned of Stu's play (log-loss 1.230 to 0.955; the whole net 0.886 to 0.900) and by construction forgets nothing
# of the other bots, which are the opponents at the gate. Publish it as train-r1/ (the first, forgetful net and the other
# variants' scores go under train-r1/variants/) and put it where the round-1 bots look for it.
set -euo pipefail
W=$HOME/work/loop; R=$W/r1; P=$W/pub/train-r1; S=$W/src
mkdir -p "$P/variants"
mv "$P/policy.npz" "$P/variants/first-3e4.policy.npz"; mv "$P/metrics.json" "$P/variants/first-3e4.metrics.json"; rm -f "$P/policy.sha256"
for v in full-1e4 full-5e5 vec-3e3 vec-1e2; do cp -f "$R/$v/metrics.json" "$P/variants/$v.metrics.json"; cp -f "$R/$v.log" "$P/variants/$v.log"; done
cp -f "$R/vec-1e2/policy.npz" "$P/policy.npz"; cp -f "$R/vec-1e2/metrics.json" "$P/metrics.json"
sha256sum "$P/policy.npz" | cut -c1-64 > "$P/policy.sha256"
cat > "$P/README.md" <<'MD'
# Stu, round 1's net (13 November 2026)

`policy.npz`: rollout net v2 (epoch 5) with one bot added, `stu0`, whose two vectors were started from `8s-32`'s and
trained on 759 boards of round 0's Stu (62,504 decisions; `scripts/train_rollout_net.py --only-vectors stu0`, rate
1e-2, epoch 6 of 8). Every other weight is v2's, bit for bit. `metrics.json` is the trainer's file for it;
`metrics_before.json` the same held-out rows (250 later boards of Stu's as bot `stu0`, joined to the plan session's
`freshB.npz` for the other bots) scored before any training. `variants/`: the same rows and held-out set with the whole
net trained at three rates, which learn a little more of Stu and forget some of the other bots.
MD
mkdir -p "$S/models/cardplay/stu-net-r1-20261113"; cp -f "$P/policy.npz" "$S/models/cardplay/stu-net-r1-20261113/policy.npz"
"$W/venv/bin/python" - <<'PY'
import numpy as np, os
W = os.path.expanduser('~/work/loop')
a = np.load(W + '/src/models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz', allow_pickle=True)
b = np.load(W + '/pub/train-r1/policy.npz', allow_pickle=True)
va, vb = [str(x) for x in a['bot_vocab']], [str(x) for x in b['bot_vocab']]
same = [k for k in a.files if k not in ('emb_own', 'emb_other', 'bot_vocab') and a[k].dtype.kind == 'f']
print('vocabulary', vb)
print('weights other than the vectors identical to v2:', all(np.array_equal(a[k], b[k]) for k in same), len(same))
print("every v2 bot's vectors identical:", all(np.array_equal(a[k][va.index(n)], b[k][vb.index(n)]) for k in ('emb_own', 'emb_other') for n in va))
i, j = va.index('8s-32'), vb.index('stu0')
print('stu0 against 8s-32: largest change', [round(float(np.abs(b[k][j] - a[k][i]).max()), 3) for k in ('emb_own', 'emb_other')], '| norms', [round(float(np.linalg.norm(b[k][j] - a[k][i])), 3) for k in ('emb_own', 'emb_other')], 'of', [round(float(np.linalg.norm(a[k][i])), 3) for k in ('emb_own', 'emb_other')])
PY
cat "$P/policy.sha256"; ls "$P" "$P/variants" | tr '\n' ' '; echo; tail -n 1 "$W/runs/l0b-stu0.log" | cut -c1-110; date -u +%FT%TZ
