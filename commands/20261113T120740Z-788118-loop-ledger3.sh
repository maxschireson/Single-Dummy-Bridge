# boxctl: timeout=300
# boxctl: timeout=300
# loop session: the fusion ledger over the ladder's records, two workers at low priority beside the ladder. The checkout
# only adds files and changes documents (the chain's scripts and job file are untouched), so the chain is not stopped.
set -euo pipefail
COMMIT=4806f1fad9aaee01a86f6860d53e6bd594b834aa
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113
git -C "$S" diff --stat HEAD "$COMMIT" | tail -5
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h %s' | cut -c1-100
mkdir -p "$W/pub/ledger"
cat > "$W/ledger.sh" <<'SH'
#!/bin/bash
# The ledger over every ladder run with records, then again each half hour as the runs grow.
W=$HOME/work/loop; S=$W/src; cd "$S"
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
while :; do
  runs=""
  for d in "$W"/runs/l*; do [ -d "$d/episodes" ] && runs="$runs $(basename "$d")=$d"; done
  nice -n 15 "$W/venv/bin/python" training/rollout-loop-20261113/fusion_ledger.py $runs --out "$W/pub/ledger/ledger.json.tmp" --workers 2 > "$W/pub/ledger/ledger.txt.tmp" 2>&1     && mv "$W/pub/ledger/ledger.json.tmp" "$W/pub/ledger/ledger.json" && { date -u +"as of %FT%TZ"; cat "$W/pub/ledger/ledger.txt.tmp"; } > "$W/pub/ledger/ledger.txt"
  sleep 1800
done
SH
chmod +x "$W/ledger.sh"
sudo systemctl stop loop-ledger 2>/dev/null || true; sudo systemctl reset-failed loop-ledger 2>/dev/null || true
sudo systemd-run --unit=loop-ledger --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$W/ledger.sh"
sleep 20; systemctl is-active loop-chain loop-publish loop-ledger | tr '\n' ' '; echo; tail -n 3 "$W/runs.log" | cut -c1-150; ls "$W/runs" | tr '\n' ' '; echo; head -c 600 "$W/pub/ledger/ledger.txt.tmp" 2>/dev/null; date -u +%FT%TZ
