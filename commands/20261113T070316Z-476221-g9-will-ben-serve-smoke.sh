# boxctl: timeout=700
#!/bin/bash
# G9: smoke test of `gen9_ben_lanes.py serve` on azure4: a BEN 64 server on the host loopback (port 8089) with the
# Gen 7 capture capsule's config, two real bidding requests, then the server stops with the command.
set -u
SRC=~/work/g9/ben-lanes-src
git -C $SRC fetch -q --depth 1 origin feature/gen9-workflow-ben-lanes && git -C $SRC checkout -q FETCH_HEAD
echo "lanes source $(git -C $SRC rev-parse --short HEAD)"
ls ~/work/capsule-gen7-capture/recovery/assets/ | grep -i ben
cat > /tmp/g9-ben-bid.py <<'PY'
import json, time
from urllib.parse import urlencode
from urllib.request import urlopen
for hand, ctx in (("AK32.KQ4.J98.A65", ""), ("QJ1098.A2.K43.Q2", "1C--")):
    q = urlencode(dict(hand=hand, seat="N", dealer="N", vul="None", ctx=ctx, matchtype="IMP", details="false"))
    t = time.time()
    with urlopen("http://127.0.0.1:8089/bid?" + q, timeout=120) as r:
        d = json.load(r)
    print(hand, repr(ctx), "->", d.get("bid"), f"{time.time() - t:.1f} s", "keys", sorted(d)[:6])
PY
cd $SRC && timeout 600 python3 ops/gen9_ben_lanes.py serve --ben-bot ben64 --source ~/work/capsule-gen7-capture/recovery -- ~/work/venv/bin/python /tmp/g9-ben-bid.py
echo "serve exit $?"
python3 -c "import socket; print('8089 free afterwards:', socket.socket().connect_ex(('127.0.0.1',8089)) != 0)"
