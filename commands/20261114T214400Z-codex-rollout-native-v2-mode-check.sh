# boxctl: timeout=900
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"
C="$W/code-v2-d82f9a7"
A="$W/acceptance-v2-d82f9a7-mode-check"
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
export STU_RUNTIME="$W/runtime" SURE_BIN="$HOME/work/loop/bin/sure_cpp"
export BRIDGE_NET_BF16=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=''
PY="$HOME/work/loop/venv/bin/python"
H="$C/scripts/stu_rollout_experiments"
test ! -e "$A"; mkdir "$A"
cp "$W/acceptance-v2-d82f9a7/bots.json" "$A/bots.json"
publish() {
  rc=$?
  printf '%s\n' "$rc" > "$A/exit-code.txt"
  date -u +%FT%TZ > "$A/finished.txt"
  D="$W/pub"
  git -C "$D" pull -q --ff-only origin transfer/stu-rollout-experiments-azure6-20261114
  cp -a "$A" "$D/v2/"
  git -C "$D" add v2
  git -C "$D" -c user.name="Codex rollout experiments" -c user.email=codex@openai.com commit -q -m "Azure6 numerical-mode acceptance evidence"
  git -C "$D" push -q origin transfer/stu-rollout-experiments-azure6-20261114
}
trap publish EXIT
date -u +%FT%TZ > "$A/started.txt"
printf '%s\n' 'Original test_x8 fixtures directly call FP32 forward and mutate params after BF16 construction; run those unmodified in FP32. Actual R4c null/zero/child acceptance runs BF16. Original failed BF16 evidence retained.' > "$A/MODE_NOTE.txt"
"$PY" "$H/native_acceptance.py" --source "$HOME/work/loop/capsule/recovery" --bots "$A/bots.json" --out "$A/native.json" > "$A/native.log" 2>&1
(cd "$STU_RUNTIME" && BRIDGE_NET_BF16=0 "$PY" -m unittest discover -s tests -p test_x8.py -v) > "$A/runtime-x8-fp32.log" 2>&1
cat "$A/native.json"
tail -5 "$A/runtime-x8-fp32.log"
