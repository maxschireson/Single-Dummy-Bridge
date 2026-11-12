# boxctl: timeout=120
# Read-only: the drained phase 1 cohort on azure3 as a source for the next Gen 7.1 lanes: state, unplayed deals not in the
# v4.1 training families, and how they split eight ways; the current lanes' remaining deals.
W=$HOME/work; R=$W/runs/gen7-phase1-azure3
echo "STOP $([ -e $R/STOP ] && echo yes || echo no), WATCHDOG_STOP $([ -e $R/WATCHDOG_STOP ] && echo yes || echo no), failures $(ls $R/failures | wc -l), receipts $(ls $R/receipts | wc -l), published $($W/venv/bin/python -c "import json; print(json.load(open('$R/publisher-status.json')).get('completed'))"), units arena-gen7 $(systemctl is-active arena-gen7) arena-gen7-publish $(systemctl is-active arena-gen7-publish)"
cd $W/sdb-gen71x && TF_CPP_MIN_LOG_LEVEL=3 $W/venv/bin/python - "$W" <<'PY' 2>/dev/null
import glob, json, os, sys
w = sys.argv[1]; sys.path.insert(0, os.getcwd())
from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load
trained = set(json.load(open(w + '/gen71/all-training-families.json')))
R = w + '/runs/gen7-phase1-azure3'; m = json.load(open(R + '/manifest.json'))
fams = [deal_key(b.hands, True) for b in load(os.path.join(R, m['corpus']))]
done = {json.load(open(p))['family'] for p in glob.glob(R + '/receipts/*.json')}
unplayed = [f for f in fams if f not in done]
fresh = [f for f in unplayed if f not in trained]
print(f"phase 1 azure3: {len(fams)} deals, {len(done)} played, {len(unplayed)} unplayed, {len(fresh)} of them not in the training families; 7s-32 identity {m['bots']['7s-32']['identity'][:12]}; source {m.get('source_commit','')[:7]}")
other = set()
for run in glob.glob(w + '/runs/*'):
    if run == R or not os.path.exists(run + '/manifest.json'): continue
    mm = json.load(open(run + '/manifest.json'))
    try: other |= {deal_key(b.hands, True) for b in load(os.path.join(run, mm['corpus']))}
    except Exception: pass
print(f"of those fresh deals, also in another run's corpus on this box: {len(set(fresh) & other)}")
left = 0
for n in range(1, 9):
    rr = f'{w}/runs/gen71fresh-azure3-ben64-{n}'; mm = json.load(open(rr + '/manifest.json')); k = len(glob.glob(rr + '/receipts/*.json')); left += mm['target'] - k
    print(f"lane {n}: {k} of {mm['target']}")
print('current lanes: deals left', left)
PY
