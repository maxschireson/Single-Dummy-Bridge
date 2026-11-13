# boxctl: timeout=1800
# boxctl: timeout=1800
# loop session: the interim round's cut on azure3: the boards of sp0b and spr0b past their last published block, built once
# (rows_cut.sh, Nice 10, two workers) into pub/rows-cut for the publisher. The checkout adds scripts only (no engine
# change since 57eb87c, the collection's source); the chains are not stopped.
set -euo pipefail
COMMIT=6514196d6d95e7ef4fdf896b63148df20d4786aa
W=$HOME/work/loop; S=$W/src
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" -- bridge_harness scripts | tail -2
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
cd "$S"; bash training/rollout-loop-20261113/rows_cut.sh sp0b spr0b
for r in sp0b spr0b; do echo "$r $(wc -l < "$W/runs/$r/results.jsonl") tables"; done
systemctl is-active loop-collect loop-collect-b loop-publish loop-rows 2>/dev/null | tr '\n' ' '; date -u +%FT%TZ
