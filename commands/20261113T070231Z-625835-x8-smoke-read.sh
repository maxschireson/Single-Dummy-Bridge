# boxctl: timeout=60
P=$HOME/work/x8/prep; $HOME/work/venv/bin/python - <<"X"
import json, os
r = json.load(open(os.environ["HOME"] + "/work/x8/prep/smoke8x.json"))
print(list(r.keys()))
for k, v in r.items():
    if k not in ("gen7_bots",): print(k, json.dumps(v)[:400])
X
grep -c . $P/smoke.log; grep -i "deal\|pair\|8x3\|error\|warn" $P/smoke.log | head -10
