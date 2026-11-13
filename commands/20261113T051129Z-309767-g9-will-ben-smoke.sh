# boxctl: timeout=1000
#!/bin/bash
# G9: smoke test of BEN on azure4 after the install: one BEN 64 server in its own namespace (g9 names, tag smoke),
# wait until it answers, measure, take it down.
set -u
cd ~/work/g9/ben-lanes-src
C=~/work/feeds/arena-gen6-chatgpt-feed/recovery/assets/ben-64.conf
timeout 700 python3 ops/gen9_ben_lanes.py up --lanes 1 --tag smoke --ben-bot ben64 --conf "$C"; echo "up exit $?"
python3 ops/gen9_ben_lanes.py status --lanes 1 --tag smoke
timeout 300 python3 ops/gen9_ben_lanes.py measure --lanes 1 --tag smoke; echo "measure exit $?"
python3 ops/gen9_ben_lanes.py down --lanes 1 --tag smoke; echo "down exit $?"
systemctl list-units --all --no-pager --plain 'g9-ben-*' | head -5
ip netns list | grep g9 || echo "no g9 namespaces left"
