# boxctl: timeout=120
# boxctl: timeout=120
# g8 (azure4, mine until 15:00 UTC at the latest): the frozen rule systems r3 and r4 against the house bidder, double
# dummy, on 32,000 deals made for this measurement only (seeds 601-608). Output: est/final-r3.txt, est/final-r4.txt.
set -uo pipefail
G=$HOME/work/g8
mkdir -p "$G/est" "$G/pub/est"
cat > "$G/final.sh" <<'SH'
#!/usr/bin/env bash
G=$HOME/work/g8; D=$G/src-tune; PY=$HOME/work/venv/bin/python; CAP=$HOME/work/capsule-gen7-capture/recovery
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
cd "$D" || exit 1
git fetch -q --depth 1 origin 663854708d4b27c402a215cea4b63028a0780a3a && git checkout -q FETCH_HEAD || { echo "could not check out" > "$G/est/final.log"; exit 1; }
: > "$G/est/final-r3.txt"; : > "$G/est/final-r4.txt"
for seed in 601 602 603 604 605 606 607 608; do
  "$PY" -u scripts/tune_rule_bidder.py measure --source "$CAP" --seed $seed --deals 4000 --cache "$G/ddcache" --workers 8 \
     --settings configs/rule-systems/precision-r4.json 2>> "$G/est/final.log" | grep '^start' | sed "s/^start/seed $seed/" >> "$G/est/final-r4.txt"
  "$PY" -u scripts/tune_rule_bidder.py measure --source "$CAP" --seed $seed --deals 4000 --cache "$G/ddcache" --workers 8 \
     --settings configs/rule-systems/precision.json 2>> "$G/est/final.log" | grep '^start' | sed "s/^start/seed $seed/" >> "$G/est/final-r3.txt"
  cp -f "$G/est/final-r3.txt" "$G/est/final-r4.txt" "$G/pub/est/"
done
echo done >> "$G/est/final.log"
SH
chmod +x "$G/final.sh"
sudo systemctl stop g8-final 2>/dev/null; sudo systemctl reset-failed g8-final 2>/dev/null
sudo systemd-run --quiet --unit=g8-final --uid="$(id -un)" --setenv=HOME="$HOME" --working-directory="$G" -- "$G/final.sh"
sleep 30; echo "unit: $(systemctl is-active g8-final); queue unit: $(systemctl is-active g8-queue) at $(cat "$G/queue.pos") of $(wc -l < "$G/queue.txt")"; tail -2 "$G/est/final.log" 2>/dev/null | cut -c1-200
