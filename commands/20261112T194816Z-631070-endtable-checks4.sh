# boxctl: timeout=5400
# boxctl: timeout=5400
# Ending table: acceptance checks on the built 4-card table (TABLE_BUILD.md section 8), after unit endtable-k4 finished.
# Logs in ~/work/endtable/checks. The split step uses the configurations of SEARCH.md's time split plus the built table.
set -uo pipefail
W=$HOME/work/endtable; SRC=$W/src; E=$SRC/experiments/sure_tricks/endtable; ST=$SRC/experiments/sure_tricks; T4=$W/tables/k4.et
systemctl is-active --quiet endtable-k4 && { echo "endtable-k4 is still running"; exit 1; }
tail -2 $W/k4-build.log
ls -la $W/tables
R=$E/azure/run_endtable.sh
for step in basic showout pooled t7; do bash $R checks4 $step || echo "STEP $step exited $?"; done
cd $ST && python3 split.py A6_8,S6_8,B6_8,A6_9,S6_9,A6_10,S6_10 8 "free=--replay" "cache=--cells 0.002 --noflush" "cold4k=--cells 2.5" "coldhuge=--cells 2.5 --huge" "table=--table $T4" 2>&1 | tee $W/checks/split.txt | tail -12
sha256sum $T4
