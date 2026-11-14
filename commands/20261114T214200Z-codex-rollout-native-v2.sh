# boxctl: timeout=900
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"
C="$W/code-v2-d82f9a7"
A="$W/acceptance-v2-d82f9a7"
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
test ! -e "$A"
mkdir "$A"
test "$(systemctl is-active stu-rollout-experiments || true)" != active
git -C "$W/code" fetch -q origin research/stu-rollout-experiments-20261114
git -C "$W/code" worktree add -q --detach "$C" d82f9a7d9884262474a6c0e37871001d70709346
export STU_RUNTIME="$W/runtime" SURE_BIN="$HOME/work/loop/bin/sure_cpp"
export BRIDGE_NET_BF16=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=''
PY="$HOME/work/loop/venv/bin/python"
H="$C/scripts/stu_rollout_experiments"
publish() {
  rc=$?
  printf '%s\n' "$rc" > "$A/exit-code.txt"
  date -u +%FT%TZ > "$A/finished.txt"
  D="$W/pub"
  git -C "$D" pull -q --ff-only origin transfer/stu-rollout-experiments-azure6-20261114
  mkdir -p "$D/v2"
  cp -a "$A" "$D/v2/"
  git -C "$D" add v2
  git -C "$D" -c user.name="Codex rollout experiments" -c user.email=codex@openai.com commit -q -m "Azure6 v2 native acceptance checkpoint"
  git -C "$D" push -q origin transfer/stu-rollout-experiments-azure6-20261114
}
trap publish EXIT
date -u +%FT%TZ > "$A/started.txt"
"$PY" "$H/make_config.py" --bots "$STU_RUNTIME/configs/loop-bots.json" --out "$A/bots.json"
"$PY" -m unittest discover -s "$H" -v > "$A/regressions.log" 2>&1
(cd "$STU_RUNTIME" && "$PY" -m unittest discover -s tests -p test_x8.py -v) > "$A/runtime-x8.log" 2>&1
"$PY" "$H/native_acceptance.py" --source "$HOME/work/loop/capsule/recovery" --bots "$A/bots.json" --out "$A/native.json" > "$A/native.log" 2>&1
cat "$A/native.json"
tail -5 "$A/regressions.log"
tail -5 "$A/runtime-x8.log"
