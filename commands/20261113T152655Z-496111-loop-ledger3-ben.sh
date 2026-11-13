# boxctl: timeout=300
# boxctl: timeout=300
# loop session: the fusion ledger on azure3 also reads the matches against BEN (eight shards a run), so BEN's own cards
# are counted. The checkout changes documents, the bots file (new bots only) and fusion_ledger.py; the BEN chain's
# scripts and job file are untouched, so nothing is stopped.
set -euo pipefail
COMMIT=fd641727af6bcaa819a51ffece408bc9c40736da
W=$HOME/work/loop; S=$W/src
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113
git -C "$S" diff --stat HEAD "$COMMIT" | tail -12
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h' 
cat > "$W/ledger.sh" <<'SH'
#!/bin/bash
# The ledger over every ladder run with records and every match against BEN (its shards pooled), again each half hour.
W=$HOME/work/loop; S=$W/src; cd "$S"
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
while :; do
  runs=""
  for d in "$W"/runs/l*; do [ -d "$d/episodes" ] && runs="$runs $(basename "$d")=$d"; done
  for b in $(ls -d "$W"/runs/b0-*-1 2>/dev/null | sed 's/-1$//'); do
    dirs=""; for n in 1 2 3 4 5 6 7 8; do [ -d "$b-$n/episodes" ] && dirs="$dirs,$b-$n"; done
    [ -n "$dirs" ] && runs="$runs $(basename "$b")=${dirs#,}"
  done
  nice -n 15 "$W/venv/bin/python" training/rollout-loop-20261113/fusion_ledger.py $runs --out "$W/pub/ledger/ledger.json.tmp" --workers 2 > "$W/pub/ledger/ledger.txt.tmp" 2>&1 \
    && mv "$W/pub/ledger/ledger.json.tmp" "$W/pub/ledger/ledger.json" && { date -u +"as of %FT%TZ"; cat "$W/pub/ledger/ledger.txt.tmp"; } > "$W/pub/ledger/ledger.txt"
  sleep 1800
done
SH
sudo systemctl stop loop-ledger 2>/dev/null || true; sudo systemctl reset-failed loop-ledger 2>/dev/null || true
sudo systemd-run --unit=loop-ledger --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$W/ledger.sh"
sleep 75; grep "^b0\|^as of" "$W/pub/ledger/ledger.txt" | cut -c1-190; tail -n 3 "$W/pub/ledger/ledger.txt.tmp" | cut -c1-190
for n in 1 2 3 4 5 6 7 8; do printf "%s " "$(wc -l < "$W/runs/b0-p-$n/results.jsonl" 2>/dev/null)"; done; echo "boards by lane (b0-p)"
systemctl is-active loop-switch loop-ledger loop-publish | tr '\n' ' '; tail -n 2 "$W/runs.log" | cut -c1-140; uptime | sed 's/.*load/load/'; date -u +%FT%TZ
