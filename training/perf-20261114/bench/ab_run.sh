#!/usr/bin/env bash
# ab_run.sh TAG DEALS FIRST [env assignments...] : one self-play run with peak worker RSS
TAG=$1; DEALS=$2; FIRST=$3; shift 3
cd "${REPO:-$(dirname "$0")/../../..}"
export SURE_BIN=${SURE_BIN:?set SURE_BIN to sure_cpp}; mkdir -p ${RUNS:-/tmp/perf-runs} OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
rm -rf ${RUNS:-/tmp/perf-runs}/$TAG
env "$@" python3 scripts/x8_match.py --source ${CAPSULE:?set CAPSULE to the capsule recovery folder} --bots configs/loop-bots.json --pair stu3-psa~stu3-psb \
  --deals $DEALS --first $FIRST --seed 777 --workers 1 --out ${RUNS:-/tmp/perf-runs}/$TAG --episodes --one-room > ${RUNS:-/tmp/perf-runs}/$TAG.log 2>&1 &
PID=$!; PEAK=0
while kill -0 $PID 2>/dev/null; do
  R=$(ps -o rss= --ppid $PID 2>/dev/null | sort -n | tail -1); R=${R:-0}; [ "$R" -gt "$PEAK" ] && PEAK=$R; sleep 2
done
echo "$TAG: $(tail -1 ${RUNS:-/tmp/perf-runs}/$TAG.log)  peak worker RSS $((PEAK/1024)) MB"
