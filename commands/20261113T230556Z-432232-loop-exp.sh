# boxctl: timeout=300
# boxctl: timeout=300
# loop session (Max, 22:26 and 22:31 UTC: label quality against volume, tables against positions): exp_labels.sh on
# azure6's stopped runs sp0c and spr0c, in a unit of its own beside the collection (4 threads at Nice 10, from the second
# checkout; the collection's source is untouched). Results to pub/exp/ (the publisher pushes them).
set -euo pipefail
COMMIT=1a40de0ca034c886228480e0d834550c7a2d19d2
W=$HOME/work/loop; S2=$W/src-lc
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q "$COMMIT"; git -C "$S2" log -1 --format='second checkout %h'
for d in bridge_harness/libbridge_dds.so models/cardplay; do [ -e "$S2/$d" ] && [ ! -L "$S2/$d" ] && rm -rf "$S2/$d"; ln -sfn "$W/src/$d" "$S2/$d"; done
[ -f "$W/src/models/cardplay/stu-net-r1-20261113/policy.npz" ] || (cd "$W/src" && bash training/rollout-loop-20261113/get_net.sh 1 a9ee66def78cea60caa54b8268791efead51e30184f2b8806f6bd8ce9932c53b)
ls "$S2/models/cardplay/stu-net-r1-20261113/policy.npz" "$S2/training/rollout-net-v2-20261113/merge_sets.py" > /dev/null
sudo systemctl reset-failed loop-exp 2>/dev/null || true
sudo systemd-run --unit=loop-exp --uid="$USER" --working-directory="$S2" --setenv=HOME="$HOME" --setenv=THREADS=4 -- bash "$S2/training/rollout-loop-20261113/exp_labels.sh" sp0c,spr0c
sleep 30; systemctl is-active loop-exp loop-collect loop-rows loop-publish | tr '\n' ' '; tail -n 3 "$W/pub/exp/timeline.log" 2>/dev/null | cut -c1-200; date -u +%FT%TZ
