# boxctl: timeout=1800
# boxctl: timeout=1800
# Ending table (experiments/sure_tricks/endtable, branch research/sure-trick-table-20261112 at c9cc58d): set up, build the
# 1-, 2- and 3-card tables, measure the 4-card evaluator, and start the 4-card build (unit endtable-k4) if the 3-card file
# equals the one built and checked in the session. azure6 assigned to this by Max, 12 November 2026, 18:18 UTC.
set -euo pipefail
COMMIT=c9cc58d99d54309d8a8cbd961801756aaef4cf4e
W=$HOME/work/endtable; SRC=$W/src
mkdir -p "$W"
command -v make >/dev/null || { echo "make is not installed"; exit 1; }
if [ ! -d "$SRC/.git" ]; then git init -q "$SRC" && git -C "$SRC" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; fi
git -C "$SRC" fetch -q --depth 5 origin research/sure-trick-table-20261112 && git -C "$SRC" checkout -q "$COMMIT"
R=$SRC/experiments/sure_tricks/endtable/azure/run_endtable.sh
bash "$R" setup "$COMMIT"
bash "$R" small
"$SRC/experiments/sure_tricks/endtable/endtable_tool" evalbench 4 "$W/tables/k3.et" 50000 3 plain
want=cfafa36d8f07976312c0ac2b4912c1f961f4221d1b388c85f781ce3b0c83c74d
got=$(sha256sum "$W/tables/k3.et" | cut -c1-64)
[ "$got" = "$want" ] || { echo "k3.et differs from the session's ($got); not starting the 4-card build"; exit 1; }
echo "k3.et equals the session's build"
bash "$R" start4
