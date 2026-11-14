# boxctl: timeout=600
# boxctl: timeout=600
# loop session (read-only, small requests): harvest.py --discover-only from the new commit into a scratch folder: which sessions
# of 2024 to 2026 the USBF pages lead to.
set -uo pipefail
W=$HOME/work/loop; S3=$HOME/work/usbc/src
[ -d "$S3/.git" ] || git clone -q --depth 3 --branch research/rollout-loop-20261113 https://github.com/maxschireson/Single-Dummy-Bridge "$S3"
git -C "$S3" fetch -q --depth 3 origin research/rollout-loop-20261113 && git -C "$S3" checkout -q d7cf8f95bca834acf5292777fb58e5ee9516423b
mkdir -p $HOME/work/usbc/disc; timeout 560 python3 "$S3/training/rollout-loop-20261113/usbc/harvest.py" $HOME/work/usbc/disc --discover-only --pause 0.15 2>&1 | tail -3
python3 - <<'PY'
import json, os, collections
s = json.load(open(os.path.expanduser('~/work/usbc/disc/sessions.json')))
u = {k: v for k, v in s.items() if v.get('from_usbf_page')}
c = collections.Counter(v['screen'] for v in u.values())
print(len(s), 'sessions;', len(u), 'from USBF pages, by screen:', dict(sorted(c.items())))
print(sorted({v['from_usbf_page'] for v in u.values()})[:20])
PY
