# boxctl: timeout=900
# boxctl: timeout=900
# loop session: where Stu and Gen 8 first play differently on each ladder board, and how those boards go (read-only
# over the records, one process at low priority). The checkout only adds a file.
set -euo pipefail
COMMIT=d71d2ee5c98155fab48b44741ff026442caff95f
W=$HOME/work/loop; S=$W/src
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h' ; mkdir -p "$W/pub/where"; cd "$S"
args=""; for r in l0-p l0-stu0 l0-pr l0-pl l0-n l0-v1 l0-v1-p; do [ -d "$W/runs/$r/episodes" ] && args="$args $r=$W/runs/$r"; done
nice -n 15 "$W/venv/bin/python" training/rollout-loop-20261113/first_divergence.py $args --out "$W/pub/where/where.json" | tee "$W/pub/where/where.txt"
tail -n 2 "$W/runs.log" | cut -c1-140; date -u +%FT%TZ
