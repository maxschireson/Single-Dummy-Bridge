# boxctl: timeout=900
# boxctl: timeout=900
# loop session: a short throwaway test of stu0-ps (the lead rolled out on the settings of every other card): CPU a table and
# collection: pure Stu's self-play, 2 workers at Nice 10, 8 training deals far from the collection's, into /tmp; from the
# second checkout (the collection's source is untouched). Then the memory now.
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q 2cb4c914eb9f7c4aead6fe6ba14d8193475201e9
cd "$S2"; export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE= BRIDGE_NET_BF16=1
rm -rf /tmp/rtest
timeout 600 nice -n 10 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair stu0-psa~stu0-psb --deals 8 --first 920000   --seed 9001 --workers 2 --out /tmp/rtest --episodes --one-room --recycle 4 2>&1 | grep -v Warning | tail -3
echo "results: $(wc -l < /tmp/rtest/results.jsonl), episodes: $(ls /tmp/rtest/episodes | wc -l)"
free -m | sed -n 2p; date -u +%FT%TZ
"$PY" -c "
import json; rows=[json.loads(l) for l in open('/tmp/rtest/results.jsonl')]
print('cpu a table', round(sum(r['cpu'] for r in rows)/len(rows),1), '| x8 summary keys:', sorted((rows[0].get('x8') or {}).get('candidate', rows[0].get('x8') or {}))[:12])
for r in rows[:3]: print({k: v for k, v in (r.get('x8') or {}).items()} if 'x8' in r else r.get('search'))
"
