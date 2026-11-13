# boxctl: timeout=120
# boxctl: timeout=120
# loop session: round 2's longer-trained variant (epoch 5 of the --select run) to the publisher as train-r2s.
set -euo pipefail
W=$HOME/work/loop; R=$W/r2; P=$W/pub/train-r2s; mkdir -p "$P"
cp -f "$R/sel/policy.npz" "$R/sel/metrics.json" "$R/sel.log" "$P/"
sha256sum "$P/policy.npz" | cut -c1-64 | tee "$P/policy.sha256"
echo "Round 2's rows (train-r2/), trained from round 1's net for up to six epochs at 1e-4 with --select stup0 --forget 0.02: epoch 5 kept." > "$P/README.txt"
ls -la "$P" | cut -c1-90; date -u +%FT%TZ
