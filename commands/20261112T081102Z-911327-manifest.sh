# boxctl: timeout=30
# Read-only: the Gen 7.1 comparison cohort's manifest (the gate script needs its bot specs; it moves to azure3 after the handoff).
python3 -c "import json,base64,zlib; print('MANZ ' + base64.b64encode(zlib.compress(open('$HOME/work/runs/gen71-vs70-fresh-azure2/manifest.json','rb').read(), 9)).decode())"
