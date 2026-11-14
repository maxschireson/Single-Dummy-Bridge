# boxctl: timeout=120
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"
test "$(systemctl is-active stu-rollout-v2-smokes || true)" != active
test "$(systemctl is-active stu-rollout-v2-publish || true)" != active
test ! -e "$W/runs-v2-d82f9a7/calibration-c1"
python3 - "$W" <<'PY'
import copy,json,pathlib,sys
w=pathlib.Path(sys.argv[1]); o=w/'runs-v2-d82f9a7'
for name in ('flat32','recursive32','selective32'):
    s=json.loads((o/f'smoke-{name}/summary.json').read_text())
    assert s['boards']==16 and not s['failures'] and not s['unfinished'] and not s['driver_failure']
bots=json.loads((o/'bots.json').read_text())
spec=copy.deepcopy(bots['rx2-recursive32'])
spec['rollout_experiment']['max_calls']=1
bots['rx2-recursive32-c1']=spec
with (o/'calibration-c1-bots.json').open('x') as f:json.dump(bots,f,indent=2)
text=(w/'publish-v2-d82f9a7.sh').read_text().replace('stu-rollout-v2-smokes','stu-rollout-v2-c1')
(w/'publish-v2-c1.sh').write_text(text)
PY
cat > "$W/run-v2-c1.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"; O="$W/runs-v2-d82f9a7"; H="$W/code-v2-d82f9a7/scripts/stu_rollout_experiments"
export STU_RUNTIME="$W/runtime" SURE_BIN="$HOME/work/loop/bin/sure_cpp"
export BRIDGE_NET_BF16=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=''
"$HOME/work/loop/venv/bin/python" "$H/match.py" --source "$HOME/work/loop/capsule/recovery" --bots "$O/calibration-c1-bots.json" --pair rx2-recursive32-c1~rx2-control --seed 2026111401 --first 2000 --deals 16 --workers 4 --recycle 4 --common-only --episodes --out "$O/calibration-c1" > "$O/calibration-c1.log" 2>&1
"$HOME/work/loop/venv/bin/python" "$H/summarize.py" "$O"
SH
sudo systemd-run --unit=stu-rollout-v2-c1 --uid=bridgebots --property=RuntimeMaxSec=1800 --property=WorkingDirectory="$W" /bin/bash "$W/run-v2-c1.sh"
sudo systemd-run --unit=stu-rollout-v2-publish-c1 --uid=bridgebots --property=RuntimeMaxSec=2100 --property=WorkingDirectory="$W" /bin/bash "$W/publish-v2-c1.sh"
systemctl show stu-rollout-v2-c1 stu-rollout-v2-publish-c1 -p Id -p ActiveState -p MainPID
