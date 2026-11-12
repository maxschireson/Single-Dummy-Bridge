# boxctl: timeout=300
# boxctl: timeout=300
# g8 (azure6): train the system scorer for the frozen rule system (rules r3 + judgement j1, the r4 system) as a unit, so it
# does not depend on my session: labelled data (60,000 + 8,000 deals at three kinds of table), then 20 minutes of
# training from the base hand-fit scorer. The file and the report go to the results branch, folder sys/.
set -uo pipefail
G=$HOME/work/g8; D=$G/src-book
[ -d "$D/.git" ] || { git init -q "$D"; git -C "$D" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; }
git -C "$D" fetch -q --depth 1 origin 663854708d4b27c402a215cea4b63028a0780a3a
git -C "$D" checkout -q FETCH_HEAD || { echo "could not check out"; exit 1; }
echo "checked out $(git -C "$D" rev-parse --short HEAD)"
mkdir -p "$G/sys" "$G/pub/sys"
cat > "$G/scorer.sh" <<'SH'
#!/usr/bin/env bash
G=$HOME/work/g8; D=$G/src-book; PY=$HOME/work/venv/bin/python; CAP=$HOME/work/capsule-gen7-capture/recovery; S=$G/sys
cd "$D" || exit 1
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
[ -f models/bidding/gen6-candidate-2026-11-11/bidder.keras ] || "$PY" models/bidding/gen6-candidate-2026-11-11/restore_model.py > /dev/null
T=rules-precision:rules-precision,rules-precision:house-gen6,house-gen6:rules-precision
{
"$PY" scripts/gen_system_fit.py "$S/v2-train.npz" --seed 6301 --deals 60000 --tables $T
"$PY" scripts/gen_system_fit.py "$S/v2-val.npz" --seed 6302 --deals 8000 --tables $T
"$PY" -u scripts/train_system_scorer.py "$S/v2-scorer.npz" --minutes 20 --val "$S/v2-val.npz" --train "$S/v2-train.npz" \
  --init "$CAP/artifacts/gen6/scorer.npz" --systems rules-precision --only rules-precision --views 1,0,0 --report "$S/v2-report.json"
echo "exit $?"
} > "$S/v2.log" 2>&1
cp -f "$S/v2-scorer.npz" "$S/v2-report.json" "$S/v2.log" "$G/pub/sys/" 2>/dev/null
SH
chmod +x "$G/scorer.sh"
sudo systemctl stop g8-scorer 2>/dev/null; sudo systemctl reset-failed g8-scorer 2>/dev/null
sudo systemd-run --quiet --unit=g8-scorer --uid="$(id -un)" --setenv=HOME="$HOME" --working-directory="$G" -- "$G/scorer.sh"
sleep 90; echo "scorer unit: $(systemctl is-active g8-scorer)"; tail -3 "$G/sys/v2.log" | cut -c1-200
