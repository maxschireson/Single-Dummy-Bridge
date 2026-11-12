# boxctl: timeout=240
# Read-only: where the v4.1 training families sit in the order of this box's current Gen 7.1 cohorts.
set -euo pipefail
W=$HOME/work; SRC=$W/sdb-gen71
[ -s $W/gen71/all-training-families.json ] || { mkdir -p $W/gen71; curl -fsS --max-time 60 -o $W/gen71/all-training-families.json https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/db4480b5fd557ff094868baf2eed64b40cfe2c4c/recovery/artifacts/validation/all-training-families.json; }
echo "list sha256 $(sha256sum $W/gen71/all-training-families.json | cut -c1-16) (expected 4818856d731bee23)"
cd "$SRC" && TF_CPP_MIN_LOG_LEVEL=3 $W/venv/bin/python - "$W" <<'PY' 2>/dev/null
import glob, json, os, sys
w = sys.argv[1]
sys.path.insert(0, os.getcwd())
from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load
trained = set(json.load(open(w + '/gen71/all-training-families.json')))
tot = dict(deals=0, played=0, hit=0, hit_played=0)
for run in sorted(glob.glob(w + '/runs/gen71-*')):
    if not os.path.exists(run + '/manifest.json') or os.path.exists(run + '/STOP'): continue
    m = json.load(open(run + '/manifest.json'))
    fams = [deal_key(b.hands, True) for b in load(os.path.join(run, m.get('corpus', 'corpus.jsonl')))]
    played = {int(os.path.basename(p)[:6]) for p in glob.glob(run + '/receipts/*.json')}
    flags = [f in trained for f in fams]
    hit = sum(flags); first_fresh = next((i for i, x in enumerate(flags) if not x), None); last_trained = max((i for i, x in enumerate(flags) if x), default=None)
    hp = sum(flags[i] for i in played)
    nxt = [i for i in range(len(fams)) if i not in played][:400]
    print(f"{os.path.basename(run)}: {len(fams)} deals, {len(played)} played (highest index {max(played, default=None)}); training families {hit}: first fresh deal at index {first_fresh}, last trained deal at index {last_trained}; "
          f"played on training families {hp}; of the next 400 deals in order, {sum(flags[i] for i in nxt)} are training families; fresh deals left {sum(1 for i in range(len(fams)) if i not in played and not flags[i])}")
    tot['deals'] += len(fams); tot['played'] += len(played); tot['hit'] += hit; tot['hit_played'] += hp
print('all current Gen 7.1 cohorts on this box:', tot)
PY
