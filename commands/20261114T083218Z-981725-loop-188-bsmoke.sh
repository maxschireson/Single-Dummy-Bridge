# boxctl: timeout=1200
# boxctl: timeout=1200
# loop session (read-only toward the collection; Nice 15, 2 workers): a smoke test of the bots on USBC deals: the old bots 1 and 6-32
# in self-play on their own auctions (3 deals each), Gen 6 against Gen 8 in the humans' contracts (3 tables), Gen 7.1 the same,
# then bot_lost_tricks.py on each.
set -uo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python; T=/tmp/usbct
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q 86265dd62af60b3038121b9327838340b1413d79
cd "$S2"; export BRIDGE_DDS_CACHE= SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1
run() { rm -rf /tmp/bs-$1; timeout 500 nice -n 15 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair "$2" --deals 3 --first 0 --seed 20260414           --workers 2 --out /tmp/bs-$1 --deals-file $T/fit_deals.json.gz --episodes --common-only $3 2>&1 | grep -v Warning | tail -1 | cut -c1-200
        "$PY" training/rollout-loop-20261113/usbc/bot_lost_tricks.py /tmp/bs-$1 /tmp/bs-$1.lt2.json.gz --tables $T/fit_tables.jsonl --label "$1" 2>&1 | tail -1; }
run own-1 "1~1-tw" ""
run own-6 "6-32~6-32-tw" ""
run hum-6 "6-32~8p-32-v41" "--book $T/fit_book.json.gz"
run hum-7 "7s-32-v41~8p-32-v41" "--book $T/fit_book.json.gz"
"$PY" - <<'PY'
import gzip, json, glob
for f in sorted(glob.glob('/tmp/bs-*.lt2.json.gz')):
    rows = [json.loads(l) for l in gzip.open(f, 'rt')]
    for r in rows[:2]:
        d = sum(x[3] for x in r['decisions'] if x[2] == 'D'); fd = sum(x[3] for x in r['decisions'] if x[2] == 'F'); l = sum(x[3] for x in r['decisions'] if x[2] == 'L')
        print(f.split('/')[-1], r['contract'], r['dec'], r['names'], 'declarer', d, 'defense', fd, 'lead', l, '| human', r.get('human_sid'), r.get('human_board'), r.get('event'))
PY
