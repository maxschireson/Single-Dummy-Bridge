# boxctl: timeout=120
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"
test "$(systemctl is-active stu-rollout-experiments || true)" != active
test "$(systemctl is-active stu-rollout-v2-smokes || true)" != active
test ! -e "$W/runs-v2-d82f9a7"
python3 - "$W/acceptance-v2-d82f9a7-mode-check/native.json" <<'PY'
import json,sys
assert json.load(open(sys.argv[1]))['status']=='passed'
PY
mkdir "$W/runs-v2-d82f9a7"
cat > "$W/run-v2-d82f9a7.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"
export STU_RUNTIME="$W/runtime" STU_EXPERIMENT_OUT="$W/runs-v2-d82f9a7"
export STU_PYTHON="$HOME/work/loop/venv/bin/python" SURE_BIN="$HOME/work/loop/bin/sure_cpp"
export BRIDGE_NET_BF16=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=''
bash "$W/code-v2-d82f9a7/scripts/stu_rollout_experiments/batch.sh"
SH
cat > "$W/publish-v2-d82f9a7.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"; D="$W/pub"; O="$W/runs-v2-d82f9a7"
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
BR=transfer/stu-rollout-experiments-azure6-20261114
for attempt in $(seq 1 65); do
  "$HOME/work/loop/venv/bin/python" "$W/code-v2-d82f9a7/scripts/stu_rollout_experiments/summarize.py" "$O"
  git -C "$D" pull -q --ff-only origin "$BR"
  python3 - "$W" "$D" "$O" <<'PY'
import json,pathlib,shutil,sys,time
w,d,o=map(pathlib.Path,sys.argv[1:])
dest=d/'v2'/o.name
for p in o.rglob('*'):
    if p.is_file() and p.suffix in ('.json','.jsonl','.md','.log') and 'episodes' not in p.parts:
        target=dest/p.relative_to(o);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
old=json.loads((w/'runs/report.json').read_text())
new=json.loads((o/'report.json').read_text())
for r in old['runs']:
    if 'recursive' in r['name'] or 'selective' in r['name']:
        r['validity']='invalid-for-inference: PR41/43; original run preserved'
for r in new['runs']:
    r['name']='v2-'+r['name'];r['source_commit']='d82f9a7d9884262474a6c0e37871001d70709346'
    r['validity']='correctness-only; not strength evidence'
combined=dict(updated=time.strftime('%FT%TZ',time.gmtime()),purpose='development only; old depth invalid, v2 correctness smokes',runs=old['runs']+new['runs'])
(d/'report.json').write_text(json.dumps(combined,indent=2)+'\n')
(d/'REPORT.md').write_text('# Rollout review correction\n\nOld recursive/selective results are invalid for inference. V2 correctness-only progress follows; source d82f9a7, native acceptance passed.\n\n'+(o/'REPORT.md').read_text())
inventory={p.parent.name:dict(count=len(list(p.glob('*.json.gz'))),path=str(p)) for p in o.glob('*/episodes')}
(dest/'EPISODES.json').write_text(json.dumps(inventory,indent=2))
PY
  git -C "$D" add -A
  if ! git -C "$D" diff --cached --quiet; then
    git -C "$D" -c user.name="Codex rollout experiments" -c user.email=codex@openai.com commit -q -m "Azure6 v2 correctness smoke progress"
    git -C "$D" push -q origin "$BR"
  fi
  if ! systemctl is-active --quiet stu-rollout-v2-smokes && [ "$attempt" -gt 1 ]; then break; fi
  sleep 60
done
SH
chmod +x "$W/run-v2-d82f9a7.sh" "$W/publish-v2-d82f9a7.sh"
sudo systemd-run --unit=stu-rollout-v2-smokes --uid=bridgebots --property=RuntimeMaxSec=3600 --property=WorkingDirectory="$W" /bin/bash "$W/run-v2-d82f9a7.sh"
sudo systemd-run --unit=stu-rollout-v2-publish --uid=bridgebots --property=RuntimeMaxSec=3900 --property=WorkingDirectory="$W" /bin/bash "$W/publish-v2-d82f9a7.sh"
systemctl show stu-rollout-v2-smokes stu-rollout-v2-publish -p Id -p ActiveState -p MainPID
