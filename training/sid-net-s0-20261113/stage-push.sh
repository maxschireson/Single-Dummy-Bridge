# Stage `push` of chain.sh (sourced): nets, scores, logs, manifests and the labels (tar parts) to a transfer branch.
# The training set itself is not kept: fetch_tips.py, the label manifest and the builder rebuild it.
BR=${BRANCH:-transfer/sid-net-s0-20261113}; D=$W/pub
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
rm -rf "$D"; git init -q "$D"; git -C "$D" checkout -q --orphan "$BR"
mkdir -p "$D/runs/s0" "$D/labels" "$D/labelsB" "$D/data"
cp -f "$W"/data/*.json "$D/data/" 2>/dev/null; cp -rf "$W/logs" "$D/"; [ -d "$W/e1" ] && cp -rf "$W/e1" "$D/"
[ -d "$W/s0" ] && cp -f "$W"/s0/*.npz "$W/s0/metrics.json" "$D/runs/s0/" 2>/dev/null
for L in labels labelsB; do
  [ -d "$W/$L" ] || continue
  cp -f "$W/$L/manifest.json" "$W/$L/stats.jsonl" "$W/$L/errors.jsonl" "$D/$L/" 2>/dev/null
  ( cd "$W/$L" && ls | grep -E '^[0-9a-f]{40}\.npz$' | sort > "$D/$L/files.txt" )
  n=$(wc -l < "$D/$L/files.txt"); parts=$(( n / 1500 + 1 ))
  split -d -a 3 -n "l/$parts" "$D/$L/files.txt" "$D/$L/list."
  for f in "$D/$L"/list.*; do tar -C "$W/$L" -cf "$D/$L/part-${f##*.}.tar" -T "$f"; rm -f "$f"; done
done
printf '%s\n' '# SiD net S_0: training outputs' '' \
  'Research data, not a feed; never merge. Made by `training/sid-net-s0-20261113/chain.sh` on' \
  '`research/sid-net-s0-20261113` (source and settings in `logs/timeline.log`; steps 1 and 2 of `experiments/sid_loop/SPEC.md`).' '' \
  '- `runs/s0`: `policy.npz` (the epoch with the best held-out card log-loss), every epoch, `metrics.json`.' \
  '- `e1/`: the student against the exact solver on held-out boards (`scripts/sid_e1.py`).' \
  '- `labels/`, `labelsB/`: the label sidecars of the training episodes and of the held-out ones (`--full`), as tar parts' \
  '  of `<episode blob id>.npz`; `manifest.json` says what they were made with, `stats.jsonl` what each episode cost.' \
  '- `data/`: the fetch manifests (the training episodes are those at the tips of rollout net v2'"'"'s last fetch) and label statistics.' \
  '- `logs/`: every stage.' > "$D/README.md"
git -C "$D" add -A
git -C "$D" -c user.name="sidnet box" -c user.email=noreply@anthropic.com commit -q -m "SiD net S_0: nets, E1, labels, manifests and logs" \
  -m "Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01N2EvxD5yoTRF2UbroPRKHK"
git -C "$D" remote add origin ssh://git@github.com/maxschireson/Single-Dummy-Bridge.git
git -C "$D" push -q -f origin "$BR" 2>&1 | tail -2
log "pushed to $BR: $(du -sh "$D" --exclude=.git | cut -f1)"
