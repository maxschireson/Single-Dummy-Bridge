# boxctl: timeout=600
# p41: the bot runtime for the tree bench on this box: a C++ compiler, DDS built in the scripts' checkout, model files restored.
# The training venv is not touched (the bench needs numpy only).
set -uo pipefail
export DEBIAN_FRONTEND=noninteractive
sudo apt-get install -y -qq build-essential python3-dev >/dev/null 2>&1; g++ --version | head -1
cd ~/work/p41src; PY=~/work/venv/bin/python
ls vendor/dds/library/src | head -3
for r in models/*/*/restore*.py; do (cd "$(dirname "$r")" && $PY "$(basename "$r")" >/dev/null 2>&1) && echo "ok $r" || echo "FAILED $r"; done 2>&1 | grep -c "^ok" 
start=$(date +%s); $PY scripts/build_dds.py 2>&1 | tail -1; echo "DDS build took $(( $(date +%s) - start ))s"; ls -la bridge_harness/libbridge_dds.so | awk '{print $5, $9}'
P=$HOME/work/p41; tail -5 $P/logs/timeline.log; echo "--- eval512"; cat $P/logs/eval512.log 2>/dev/null | cut -c1-1300 | head -60
