# boxctl: timeout=240
# Read-only: which of this box's own runs played the training-family deals that sit in its current Gen 7.1 cohort,
# and how each run was derived (source cohort, shard).
set -euo pipefail
W=$HOME/work; SRC=$W/sdb-gen71
cd "$SRC" && TF_CPP_MIN_LOG_LEVEL=3 $W/venv/bin/python - "$W" <<'PY' 2>/dev/null
import glob, json, os, sys
w = sys.argv[1]
sys.path.insert(0, os.getcwd())
from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load
trained = set(json.load(open(w + '/gen71/all-training-families.json')))
info = {}
for run in sorted(glob.glob(w + '/runs/*')):
    if not os.path.exists(run + '/manifest.json'): continue
    m = json.load(open(run + '/manifest.json')); name = os.path.basename(run)
    try: fams = [deal_key(b.hands, True) for b in load(os.path.join(run, m.get('corpus', 'corpus.jsonl')))]
    except Exception: fams = []
    played = set()
    for p in glob.glob(run + '/receipts/*.json'): played.add(json.load(open(p))['family'])
    info[name] = dict(fams=fams, played=played, m=m)
    print(f"{name}: identity {m['identity'][:12]}, deals {len(fams)}, played {len(played)}, source cohort {str(m.get('source_generation'))[:12]} (it had played {m.get('source_completed')}), shard {m.get('shard')}, corpus {str(m.get('corpus_sha256'))[:10]}")
cur = [n for n in info if n.startswith('gen71-') and not os.path.exists(f'{w}/runs/{n}/STOP')]
for n in cur[:1] if len(cur) == 1 else cur[:2]:
    hit = [f for f in info[n]['fams'] if f in trained]
    print(f"{n}: {len(hit)} training-family deals; played on this box by:")
    left = set(hit)
    for other, o in info.items():
        if other == n: continue
        k = len(set(hit) & o['played'])
        if k: print(f"   {other}: {k}"); left -= o['played']
    print(f"   not played by any run on this box: {len(left)}")
    in_pool = {}
    for other, o in info.items():
        if other == n: continue
        k = len(set(info[n]['fams']) & set(o['fams']))
        if k: in_pool[other] = k
    print('   deals of this cohort that are also in the corpus of:', in_pool)
PY
