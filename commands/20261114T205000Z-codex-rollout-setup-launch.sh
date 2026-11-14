# boxctl: timeout=600
set -euo pipefail
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
W="$HOME/work/rollout-experiments-20261114"
SRC="$HOME/work/loop/src"
PIN=30e30af88ea196b8189ff39491c83cf531797868
git clone -q --filter=blob:none --no-checkout --depth 1 --single-branch --branch research/stu-rollout-experiments-20261114 ssh://git@github.com/maxschireson/Single-Dummy-Bridge.git "$W/code"
git -C "$W/code" sparse-checkout set scripts/stu_rollout_experiments docs
git -C "$W/code" checkout -q
test "$(git -C "$W/code" rev-parse HEAD)" = 7c79acfaa138a29d140dfef3d50f9a52216a24aa
git -C "$SRC" worktree add --no-checkout --detach "$W/runtime" "$PIN"
git -C "$W/runtime" sparse-checkout set bridge_harness scripts configs tests native
git -C "$W/runtime" checkout -q --detach "$PIN"
cp "$SRC/bridge_harness/libbridge_dds.so" "$W/runtime/bridge_harness/"
mkdir -p "$W/runtime/models/cardplay/stu-net-r4c-20261113"
cp "$SRC/models/cardplay/stu-net-r4c-20261113/policy.npz" "$W/runtime/models/cardplay/stu-net-r4c-20261113/"
MODEL="$W/runtime/models/cardplay/stu-net-r4c-20261113/policy.npz"
test "$(sha256sum "$MODEL" | cut -c1-64)" = e4b689c87db2f56b98221a491757dbf348ddaea066e016f06a9331fc671197f2
STU_RUNTIME="$W/runtime" OPENBLAS_NUM_THREADS=1 "$HOME/work/loop/venv/bin/python" "$W/code/scripts/stu_rollout_experiments/test_smoke.py" -v
mkdir -p "$W/runs"
cat > "$W/run.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"
export STU_RUNTIME="$W/runtime" STU_EXPERIMENT_OUT="$W/runs"
export STU_PYTHON="$HOME/work/loop/venv/bin/python" SURE_BIN="$HOME/work/loop/bin/sure_cpp"
export BRIDGE_NET_BF16=1
for attempt in $(seq 1 80); do
  if [ -f "$W/drain-status.json" ] && "$STU_PYTHON" -c 'import json,sys;sys.exit(json.load(open(sys.argv[1]))["status"]!="drained")' "$W/drain-status.json" && ! systemctl is-active --quiet loop-collect; then
    break
  fi
  if [ "$attempt" = 80 ]; then echo 'Drain not complete; experiments not launched'; exit 1; fi
  sleep 15
done
"$STU_PYTHON" - "$W" <<'PY'
from pathlib import Path
import hashlib,json,subprocess,sys,time
w=Path(sys.argv[1]); r=w/'runtime'
files=['bridge_harness/x8_player.py','bridge_harness/x8_rollout.py','bridge_harness/gen7.py','bridge_harness/libbridge_dds.so','models/cardplay/stu-net-r4c-20261113/policy.npz']
p=dict(started=time.strftime('%FT%TZ',time.gmtime()),runtime=subprocess.check_output(['git','-C',str(r),'rev-parse','HEAD'],text=True).strip(),implementation=subprocess.check_output(['git','-C',str(w/'code'),'rev-parse','HEAD'],text=True).strip(),bf16=True,seed=2026111401,training_excluded=True,files={f:hashlib.sha256((r/f).read_bytes()).hexdigest() for f in files})
(w/'runs/provenance.json').write_text(json.dumps(p,indent=2))
PY
bash "$W/code/scripts/stu_rollout_experiments/batch.sh"
SH
chmod +x "$W/run.sh"
cat > "$W/publish.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"; D="$W/pub"
BR=transfer/stu-rollout-experiments-azure6-20261114
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
git init -q "$D"
git -C "$D" remote add origin ssh://git@github.com/maxschireson/Single-Dummy-Bridge.git
git -C "$D" checkout -q --orphan "$BR"
for attempt in $(seq 1 200); do
  "$HOME/work/loop/venv/bin/python" "$W/code/scripts/stu_rollout_experiments/summarize.py" "$W/runs"
  python3 - "$W" "$D" <<'PY'
from pathlib import Path
import json,shutil,sys
w,d=map(Path,sys.argv[1:])
for p in (w/'runs').rglob('*'):
    if p.is_file() and p.suffix in ('.json','.jsonl','.md','.log') and 'episodes' not in p.parts:
        dest=d/p.relative_to(w/'runs');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
for name in ('drain-status.json','collection-resume.json'):
    if (w/name).exists():shutil.copy2(w/name,d/name)
inventory={p.parent.name:dict(count=len(list(p.glob('*.json.gz'))),path=str(p)) for p in (w/'runs').glob('*/episodes')}
(d/'EPISODES.json').write_text(json.dumps(inventory,indent=2))
PY
  git -C "$D" add -A
  if ! git -C "$D" diff --cached --quiet; then
    git -C "$D" -c user.name="Codex rollout experiments" -c user.email=codex@openai.com commit -q -m "Azure6 rollout experiment progress"
    git -C "$D" push -q origin "$BR"
  fi
  if ! systemctl is-active --quiet stu-rollout-experiments && [ "$attempt" -gt 1 ]; then break; fi
  sleep 120
done
SH
sudo systemd-run --unit=stu-rollout-experiments --uid="$USER" --property=RuntimeMaxSec=21600 --working-directory="$W/code" bash "$W/run.sh"
sudo systemd-run --unit=stu-rollout-publish --uid="$USER" --property=RuntimeMaxSec=22200 bash "$W/publish.sh"
cat "$W/drain-status.json"
systemctl show stu-rollout-experiments loop-collect loop-publish loop-rows -p Id -p ActiveState -p MainPID
