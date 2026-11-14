# boxctl: timeout=900
# boxctl: timeout=900
# loop session (read-only; Nice 15): make_tests.py on the USBC sessions harvested so far on this box: how many human auctions fit
# the common bidder; then a smoke test of gen8_match --deals-file with the book (Gen 8 card play against itself, 4 tables).
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q 12266223f404a939dc7541f8ddfb86e2ae82efb9
ln -sfn "$W/src/bridge_harness/libbridge_dds.so" "$S2/bridge_harness/libbridge_dds.so"; ln -sfn "$W/src/models/cardplay" "$S2/models/cardplay" 2>/dev/null || true
cd "$S2"; export BRIDGE_DDS_CACHE= SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1
ls "$W/pub/usbc" | wc -l
time nice -n 15 "$PY" training/rollout-loop-20261113/usbc/make_tests.py "$W/pub/usbc" /tmp/usbct --source "$W/capsule/recovery" 2>&1 | grep -v Warning | tail -9
rm -rf /tmp/usbcsmoke; timeout 600 nice -n 15 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair 8p-32-v41~8p-32-v41   --deals 4 --first 0 --seed 20260414 --workers 2 --out /tmp/usbcsmoke --deals-file /tmp/usbct/fit_deals.json.gz --book /tmp/usbct/fit_book.json.gz --common-only --episodes 2>&1 | grep -v Warning | tail -2
"$PY" - <<'PY'
import json, gzip, glob
t = [json.loads(l) for l in open('/tmp/usbct/fit_tables.jsonl')][:4]
for f, r in zip(sorted(glob.glob('/tmp/usbcsmoke/episodes/*.json.gz')), t):
    d = json.load(gzip.open(f, 'rt')); e = next(iter(d['unique_tables'].values()))
    print(r['sid'], r['board'], r['room'], 'human auction', ' '.join(r['calls']), '| played', e['board'].get('contract'), ' '.join(e['board'].get('auction') or []))
PY
