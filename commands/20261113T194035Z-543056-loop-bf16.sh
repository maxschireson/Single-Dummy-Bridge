# boxctl: timeout=2400
# boxctl: timeout=2400
# loop session (Max, 19:32 UTC: "Prioritize bf16 first"): torch's CPU build in its own venv (~/work/loop/venv-t; the
# loop's venv is untouched), then the bf16 benchmark on rollout net v2, round 2's net and policy v4.1 (the table net,
# which also weights the layouts), on round 2's held-out rows. The collection is paused for the timing (one quiet core
# matters) and restarted after; boards in hand are lost, every finished board kept.
set -euo pipefail
COMMIT=c04692e5c74f276bbd22b930e47810c1a78901bf
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
[ -x "$W/venv-t/bin/python" ] || python3 -m venv "$W/venv-t"
"$W/venv-t/bin/pip" install -q numpy==2.5.4 2>&1 | tail -1
"$W/venv-t/bin/pip" install -q torch --index-url https://download.pytorch.org/whl/cpu 2>&1 | tail -2
"$W/venv-t/bin/python" -c "import torch; print('torch', torch.__version__, '| mkldnn', torch.backends.mkldnn.is_available()); print(torch.__config__.show().splitlines()[0:3])" 2>&1 | tail -4
sudo systemctl stop loop-collect loop-collect-b
sleep 5; uptime | sed 's/.*load/load/'
cd "$S"; export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
timeout 1500 "$W/venv-t/bin/python" training/rollout-loop-20261113/bench/bf16.py --rows "$W/r2/val.npz"   models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz models/cardplay/stu-net-r2-20261113/policy.npz   models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz 2>&1 | tail -22 || echo "bench failed"
ONEDNN_VERBOSE=1 timeout 300 "$W/venv-t/bin/python" - <<'PY' 2>&1 | grep -m3 -i "brg\|avx512\|bf16\|isa" | cut -c1-200
import torch; torch.set_num_threads(1)
a = torch.randn(512, 768).bfloat16(); b = torch.randn(768, 768).bfloat16(); (a @ b).sum()
PY
sudo systemctl reset-failed loop-collect loop-collect-b 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure5.txt"
sudo systemd-run --unit=loop-collect-b --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure5b.txt"
sleep 15; systemctl is-active loop-collect loop-collect-b | tr '\n' ' '; date -u +%FT%TZ
