# boxctl: timeout=120
# Read-only: deal pools on this box for the next Gen 7.1 cohort: every run folder with a manifest, its unplayed deals not in the
# v4.1 training families and not in the current cohort, and whether its 7s-32 is the phase 1 bot.
W=$HOME/work
cd $W/sdb-gen71x && TF_CPP_MIN_LOG_LEVEL=3 $W/venv/bin/python - "$W" <<'PY' 2>/dev/null
import glob, json, os, sys
w = sys.argv[1]; sys.path.insert(0, os.getcwd())
from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load
trained = set(json.load(open(w + '/gen71/all-training-families.json')))
cur = json.load(open(w + '/runs/gen71-mix-azure1/manifest.json'))
curf = {deal_key(b.hands, True) for b in load(os.path.join(w, 'runs/gen71-mix-azure1', cur['corpus']))}
ref = cur['bots']['7s-32']
dirs = sorted(set(os.path.dirname(p) for p in glob.glob(w + '/**/manifest.json', recursive=True)))
for d in dirs:
    try:
        m = json.load(open(d + '/manifest.json'))
        if 'corpus' not in m: continue
        fams = [deal_key(b.hands, True) for b in load(os.path.join(d, m['corpus']))]
    except Exception as e:
        continue
    played = {json.load(open(p)).get('family') for p in glob.glob(d + '/receipts/*.json')}
    fresh = [f for f in fams if f not in played and f not in trained and f not in curf]
    same = m.get('bots', {}).get('7s-32') == ref
    print(f"{d.replace(w, '~/work')}: identity {str(m.get('identity'))[:12]}, deals {len(fams)}, played {len(played)}, fresh unplayed not in the current cohort {len(fresh)}, STOP {os.path.exists(d + '/STOP')}, 7s-32 is the phase 1 bot: {same}, generation {m.get('generation')}")
PY
