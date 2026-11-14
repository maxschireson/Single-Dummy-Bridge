# boxctl: timeout=120
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"; O="$W/runs-v2-d82f9a7"
test "$(systemctl is-active stu-rollout-v2-c1 || true)" != active
test "$(systemctl is-active stu-rollout-v2-publish-c1 || true)" != active
test ! -e "$O/extended-recursive32"
python3 - "$W" <<'PY'
import pathlib,sys,json
w=pathlib.Path(sys.argv[1]);o=w/'runs-v2-d82f9a7'
s=json.loads((o/'smoke-recursive32/summary.json').read_text())
assert s['boards']==16 and s['failures']==0 and not s['driver_failure']
(w/'publish-r4c512.sh').write_text((w/'publish-v2-d82f9a7.sh').read_text().replace('stu-rollout-v2-smokes','stu-rollout-r4c512').replace('seq 1 65','seq 1 200'))
(o/'R4C512_PLAN.json').write_text(json.dumps(dict(purpose='Max requested continued R4c128 control alongside BEN; larger development screen, not promotion',source='d82f9a7d9884262474a6c0e37871001d70709346',seed=2026111401,first=6000,deals=512,workers=8,arms=['recursive32','flat32'],control='rx2-control',training_excluded=True,budget_seconds=10800),indent=2))
PY
cat > "$W/run-r4c512.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"; O="$W/runs-v2-d82f9a7"; H="$W/code-v2-d82f9a7/scripts/stu_rollout_experiments"
export STU_RUNTIME="$W/runtime" SURE_BIN="$HOME/work/loop/bin/sure_cpp"
export BRIDGE_NET_BF16=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=''
PY="$HOME/work/loop/venv/bin/python"
for arm in recursive32 flat32; do
  "$PY" "$H/match.py" --source "$HOME/work/loop/capsule/recovery" --bots "$O/bots.json" --pair "rx2-$arm~rx2-control" --seed 2026111401 --first 6000 --deals 512 --workers 8 --recycle 8 --common-only --episodes --out "$O/extended-$arm" > "$O/extended-$arm.log" 2>&1
  "$PY" "$H/summarize.py" "$O"
done
SH
sudo systemd-run --unit=stu-rollout-r4c512 --uid=bridgebots --property=RuntimeMaxSec=10800 --property=WorkingDirectory="$W" /bin/bash "$W/run-r4c512.sh"
sudo systemd-run --unit=stu-rollout-r4c512-publish --uid=bridgebots --property=RuntimeMaxSec=11000 --property=WorkingDirectory="$W" /bin/bash "$W/publish-r4c512.sh"
systemctl show stu-rollout-r4c512 stu-rollout-r4c512-publish -p Id -p ActiveState -p MainPID
