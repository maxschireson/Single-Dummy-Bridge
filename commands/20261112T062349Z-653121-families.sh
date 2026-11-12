# boxctl: timeout=240
# Read-only: how many deals of this box's Gen 7 and Gen 7.1 cohorts belong to families the policy net v4.1 was trained on
# (the independent collector's list, recovery/artifacts/validation/all-training-families.json on arena-gen71-independent-feed).
set -euo pipefail
W=$HOME/work; SRC=$W/sdb-gen71
[ -d "$SRC" ] || SRC=$(ls -d $W/sdb-gen7* | head -1)
mkdir -p $W/gen71
curl -fsS --max-time 60 -o $W/gen71/all-training-families.json https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/db4480b5fd557ff094868baf2eed64b40cfe2c4c/recovery/artifacts/validation/all-training-families.json
echo "list sha256 $(sha256sum $W/gen71/all-training-families.json | cut -c1-16) (expected 4818856d731bee23)"
cd "$SRC" && TF_CPP_MIN_LOG_LEVEL=3 $W/venv/bin/python - "$W" <<'PY' 2>/dev/null
import glob, json, os, sys
w = sys.argv[1]
sys.path.insert(0, os.getcwd())
from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load
trained = set(json.load(open(w + '/gen71/all-training-families.json')))
print('training families:', len(trained))
for run in sorted(glob.glob(w + '/runs/*')):
    if not os.path.exists(run + '/manifest.json'): continue
    m = json.load(open(run + '/manifest.json'))
    try: boards = list(load(os.path.join(run, m.get('corpus', 'corpus.jsonl'))))
    except Exception as e: print(os.path.basename(run), 'corpus not readable:', repr(e)[:80]); continue
    fams = [deal_key(b.hands, True) for b in boards]
    played = {}
    for p in glob.glob(run + '/receipts/*.json'):
        r = json.load(open(p)); played[r['family']] = r
    hit = [f for f in fams if f in trained]
    hit_played = [f for f in hit if f in played]
    by_pair = {}
    for f in hit_played: by_pair[played[f]['pair']] = by_pair.get(played[f]['pair'], 0) + 1
    print(f"{os.path.basename(run)}: {len(fams)} deals, {len(played)} played, STOP {os.path.exists(run + '/STOP')}; in the v4.1 training families: {len(hit)} deals ({100 * len(hit) / max(1, len(fams)):.1f}%), "
          f"of them played {len(hit_played)} {by_pair if by_pair else ''}, still to play {len(hit) - len(hit_played)}")
PY
