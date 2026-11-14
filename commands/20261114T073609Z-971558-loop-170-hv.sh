# boxctl: timeout=60
# boxctl: timeout=60
# loop session (read-only): USBC harvest and scoring progress.
W=$HOME/work/loop
echo "records $(ls $W/pub/usbc/*.json.gz 2>/dev/null | wc -l) | scored $(ls $W/pub/usbc-lt/*.lt.json.gz 2>/dev/null | wc -l) | units $(systemctl is-active loop-usbc loop-usbclt | tr '\n' ' ')"
grep -c "sessions found" $W/usbc.log; tail -n 1 $W/usbc.log | cut -c1-140
python3 - <<'PY'
import json, os, collections
p = os.path.expanduser('~/work/loop/pub/usbc/sessions.json')
if os.path.exists(p):
    s = json.load(open(p)); c = collections.Counter()
    for sid, m in s.items():
        name = m.get('namePlus') or m.get('name') or ('screen ' + str(m.get('screen')))
        c[(m.get('startDateTime') or '????')[:4] + ' ' + name.split(' ')[0]] += 1
    print(len(s), dict(sorted(c.items())))
PY
