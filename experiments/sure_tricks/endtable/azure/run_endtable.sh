#!/usr/bin/env bash
# The ending-table build on a box (azure6, assigned by Max on 12 November 2026, 18:18 UTC). Run through boxctl.
#
#   run_endtable.sh setup COMMIT   fetch branch research/sure-trick-table-20261112 at COMMIT into ~/work/endtable/src, build
#   run_endtable.sh small          build the 1-, 2- and 3-card tables, verify them, print hashes
#   run_endtable.sh start4         start the 4-card build as systemd unit endtable-k4 (8 threads, resumable)
#   run_endtable.sh status         progress of the 4-card build
#   run_endtable.sh checks4 [step] acceptance checks on the 4-card table (TABLE_BUILD.md section 8); logs in ~/work/endtable/checks
#
# Tables go to ~/work/endtable/tables (not committed; where they are kept for good is Max's decision).
set -euo pipefail
W=$HOME/work/endtable; SRC=$W/src; TB=$W/tables; CK=$W/checks
E=$SRC/experiments/sure_tricks/endtable; ST=$SRC/experiments/sure_tricks
BRANCH=research/sure-trick-table-20261112
UNIT=endtable-k4
PY=python3
say() { echo "$(date -u +%T) $*"; }
mkdir -p "$W" "$TB" "$CK"

cmd_setup() {
  local commit=$1
  if [ ! -d "$SRC/.git" ]; then git init -q "$SRC" && git -C "$SRC" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; fi
  git -C "$SRC" fetch -q --depth 5 origin "$BRANCH" && git -C "$SRC" checkout -q "$commit" || { say "could not check out $commit"; exit 1; }
  say "checkout: $(git -C "$SRC" log -1 --format='%H %s' | cut -c1-110)"
  say "compiler: $(g++ --version | head -1); python: $($PY --version 2>&1)"
  make -C "$E" endtable_build endtable_tool >/dev/null
  (cd "$ST" && g++ -O2 -march=native -std=c++17 -DENDTABLE -o sure_cpp sure.cpp)       # sure_cpp with the table hook (T7)
  say "built: $(cd "$E" && sha256sum endtable_build endtable_tool | cut -c1-16 | tr '\n' ' ')"
  "$E/endtable_tool" sizes
}

cmd_small() {
  cd "$E"
  ./endtable_build 1 "$TB/k1.et" --plain 2>/dev/null
  ./endtable_build 2 "$TB/k2.et" --prev "$TB/k1.et" --plain 2>/dev/null
  ./endtable_build 3 "$TB/k3.et" --prev "$TB/k2.et" --plain 2>/dev/null
  for k in 1 2 3; do ./endtable_tool verify "$TB/k$k.et"; done
  (cd "$TB" && sha256sum k1.et k2.et k3.et)
  ./endtable_tool vectors ../endtable_vectors.jsonl 1="$TB/k1.et" 2="$TB/k2.et" 3="$TB/k3.et"
}

cmd_start4() {
  if systemctl is-active --quiet "$UNIT"; then say "$UNIT is already running"; exit 1; fi
  [ -e "$TB/k4.et" ] && { say "$TB/k4.et exists; not rebuilding"; exit 1; }
  sudo systemctl reset-failed "$UNIT" 2>/dev/null || true
  sudo systemd-run --unit="$UNIT" --uid="$(id -un)" --working-directory="$E" \
    --property=StandardOutput=append:"$W/k4-build.log" --property=StandardError=append:"$W/k4-build.log" \
    -- "$E/endtable_build" 4 "$TB/k4.et" --prev "$TB/k3.et" --plain --threads "$(nproc)"
  sleep 5
  systemctl is-active "$UNIT" || true
  tail -3 "$W/k4-build.log"
}

cmd_status() {
  say "$UNIT: $(systemctl is-active "$UNIT" 2>/dev/null || true); load $(cut -d' ' -f1-3 /proc/loadavg); memory available $(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo) MB; disk free $(df -h --output=avail "$W" | tail -1)"
  tail -3 "$W/k4-build.log" 2>/dev/null || true
  ls -la "$TB"
}

cmd_checks4() {
  local step=${1:-all} T4=$TB/k4.et
  [ -e "$T4" ] || { say "no $T4"; exit 1; }
  cd "$E"
  run() { local name=$1; shift; say "== $name"; "$@" 2>&1 | tee "$CK/$name.txt" | tail -20; }
  case $step in all|basic)
    run verify ./endtable_tool verify "$T4"
    run vectors ./endtable_tool vectors ../endtable_vectors.jsonl 1="$TB/k1.et" 2="$TB/k2.et" 3="$TB/k3.et" 4="$T4"
    run roundtrip ./endtable_tool roundtrip 4 100000000 13
    run transform ./endtable_tool transform 4 1000000 11
    run mono ./endtable_tool mono "$T4" 1000000 5
    run slotbench ./endtable_tool slotbench "$T4" 2000000 3 ;;
  esac
  case $step in all|showout)
    ./endtable_tool showout "$T4" 1000000 21 "$CK/k4_showout_expect.txt" > "$CK/k4_showout_lines.txt"
    (cd "$ST" && ./sure_cpp --value --keep --ttbits 22 < "$CK/k4_showout_lines.txt" > "$CK/k4_showout_cpp.jsonl")
    run showout $PY compare_showout.py "$CK/k4_showout_expect.txt" "$CK/k4_showout_lines.txt" "$CK/k4_showout_cpp.jsonl" 30 ;;
  esac
  case $step in all|pooled)
    local n=$(nproc) i
    for i in $(seq 1 "$n"); do $PY check_values.py "$T4" $(( (2000 + n - 1) / n )) $((100 + i)) any > "$CK/pooled_$i.txt" 2>&1 & done
    wait
    say "== pooled"; cat "$CK"/pooled_*.txt | tee "$CK/pooled.txt" ;;
  esac
  case $step in all|t7)
    cd "$ST"
    run t7_5 $PY check_cpp.py 5 250 --front 4 --table "$T4"
    run t7_6 $PY check_cpp.py 6 30 --front 4 --table "$T4"
    run t7_bench $PY endtable/compare_bench.py "$T4" ;;
  esac
  case $step in all|split)
    cd "$ST"
    # the configurations of SEARCH.md's time split, and the built table; split.py also asserts equal card values
    run split $PY split.py A6_8,S6_8,B6_8,A6_9,S6_9,A6_10,S6_10 8 "free=--replay" "cache=--cells 0.002 --noflush" \
      "cold4k=--cells 2.5" "coldhuge=--cells 2.5 --huge" "table=--table $T4" ;;
  esac
}

cmd=${1:?command}; shift
"cmd_$cmd" "$@"
