# boxctl: timeout=7200
# boxctl: timeout=7200
# loop session: the interim round (r3a) on azure5 beside the collection (4 threads at Nice 10): pure Stu's tables on
# azure5 (spr0 then sp0, the 150 newest of spr0 held out) and every row block and cut file the other four boxes have
# published (fetch_rows.sh CUT=1), from round 1's net, 4 epochs at 1e-4, the epoch best on pure Stu's held-out cards with
# the other bots' log-loss within 0.02 of the start. Then indicator 1 with paired standard errors (regret_pairs.py)
# against the starting net and against round 2's net. The checkout adds files and bots; the chains are not stopped.
set -euo pipefail
COMMIT=491b9146d3639611b6646dfc4a735eb7343f39fb
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" -- bridge_harness scripts | tail -2
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'; cd "$S"
want="azure3:sp0b,spr0b azure6:sp0c,spr0c azure2:sp0d,spr0d azure1:sp0e,spr0e"
for i in $(seq 1 25); do                     # the cut files reach the branches with each box's publisher (every ten minutes)
  missing=""
  for b in $want; do box=${b%%:*}; D=$W/in/git-$box; [ -d "$D/.git" ] || git init -q "$D"
    git -C "$D" fetch -q --depth 1 https://github.com/maxschireson/Single-Dummy-Bridge "transfer/rollout-loop-$box-20261113"
    for r in $(echo "${b#*:}" | tr ',' ' '); do git -C "$D" ls-tree --name-only FETCH_HEAD rows-cut/ 2>/dev/null | grep -q "^rows-cut/$r-" || missing="$missing $box:$r"; done
  done
  [ -z "$missing" ] && break; [ "$i" = 25 ] && echo "going on without cut files for:$missing"; sleep 60
done
CUT=1 bash $T/fetch_rows.sh azure3 azure6 azure2 azure1
EXTRA=$(ls "$W"/in/rows-azure*/*.npz "$W"/in/cut-azure*/*.npz 2>/dev/null | tr '\n' ' ')
echo "spr0 $(wc -l < "$W/runs/spr0/results.jsonl") tables, sp0 $(wc -l < "$W/runs/sp0/results.jsonl"); $(echo $EXTRA | wc -w) row files from the other boxes"
THREADS=4 SELECT=stup0 FORGET=0.02 EXTRA="$EXTRA" bash $T/round2.sh r3a spr0,sp0 150 4 1e-4 > "$W/r3a.out" 2>&1 || { echo "round2.sh failed"; tail -n 15 "$W/r3a.out"; exit 1; }
cut -c1-235 "$W/r3a/timeline.log"
mkdir -p "$S/models/cardplay/stu-net-r3a-20261113"; cp -f "$W/r3a/net/policy.npz" "$S/models/cardplay/stu-net-r3a-20261113/policy.npz"
R2=$S/models/cardplay/stu-net-r2-20261113/policy.npz
export OPENBLAS_NUM_THREADS=4 OMP_NUM_THREADS=4
echo "== indicator 1: round 1's net (start) -> r3a"; nice -n 10 "$W/venv/bin/python" $T/regret_pairs.py "$W/r3a/val.npz" "$W/r3a/before/policy.npz" "$W/r3a/net/policy.npz" --json "$W/pub/train-r3a/regret_start.json"
echo "== round 2's net -> r3a";               nice -n 10 "$W/venv/bin/python" $T/regret_pairs.py "$W/r3a/val.npz" "$R2" "$W/r3a/net/policy.npz" --json "$W/pub/train-r3a/regret_r2.json"
sha256sum "$S/models/cardplay/stu-net-r3a-20261113/policy.npz" | cut -c1-64
systemctl is-active loop-collect loop-collect-b loop-publish | tr '\n' ' '; date -u +%FT%TZ
