# boxctl: timeout=1500
# boxctl: timeout=1500
# loop session: round 2's training on azure5 beside the collection (4 threads at Nice 10): pure Stu's tables so far
# (spr0 and sp0), the 150 most recent of spr0 held out, from round 1's net with as many replay rows. Then the net is put
# where round 2's bots read it on this box. The checkout adds files and bots; the collection chains are not stopped.
set -euo pipefail
COMMIT=3435a1b007441f6e119cfecc9243062c96ff8a3d
W=$HOME/work/loop; S=$W/src
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
echo "spr0 $(wc -l < "$W/runs/spr0/results.jsonl") tables, sp0 $(wc -l < "$W/runs/sp0/results.jsonl")"
cd "$S"; THREADS=4 bash training/rollout-loop-20261113/round2.sh r2 spr0,sp0 150 4 1e-4 > "$W/r2.out" 2>&1 || { echo "round2.sh failed"; tail -n 15 "$W/r2.out"; exit 1; }
cut -c1-235 "$W/r2/timeline.log"
mkdir -p "$S/models/cardplay/stu-net-r2-20261113"; cp -f "$W/r2/net/policy.npz" "$S/models/cardplay/stu-net-r2-20261113/policy.npz"
sha256sum "$S/models/cardplay/stu-net-r2-20261113/policy.npz" | cut -c1-64; ls -la "$W/pub/train-r2/" | cut -c1-100
systemctl is-active loop-collect loop-collect-b loop-publish | tr '\n' ' '; date -u +%FT%TZ
