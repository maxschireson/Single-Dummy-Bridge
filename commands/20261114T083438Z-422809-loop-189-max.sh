# boxctl: timeout=60
# boxctl: timeout=60
W=$HOME/work/loop
echo "records $(ls $W/pub/usbc/*.json.gz | wc -l) lt2 $(ls $W/pub/usbc-lt/*.lt2.json.gz | wc -l) | $(systemctl is-active loop-usbc25 loop-usbclt | tr '\n' ' ')"; tail -n 1 $W/usbc25.log | cut -c1-120
python3 - <<'PY'
import gzip, json, glob, os, collections
hits = collections.Counter()
for f in glob.glob(os.path.expanduser('~/work/loop/pub/usbc/usbc_*.json.gz')):
    d = json.load(gzip.open(f, 'rt'))
    for t in d.get('teams', []):
        for p in t.get('players', []):
            n = p.get('name') or ''
            if 'schireson' in n.lower() or n.lower().startswith('max '):
                hits[(n, d['meta'].get('namePlus') or d['meta'].get('name') or d['miniSessionId'], t.get('name'))] += 1
for k, v in sorted(hits.items()): print(v, k)
PY
