# boxctl: timeout=1500
# Pre-7 test match on this box: 7s-32 (candidate settings) against 6-32 on this box's own block of deals,
# published every ten minutes to transfer/pre7-test-<box>-20261112. Asked for by Max, 12 Nov 02:19 UTC.
set -euo pipefail
BOX=$BOXCTL_BOX
SHA=95b8380345e8ff70708ae0fdf9af0c4bf6b374dc
CAPSULE=8833c62f83687293ad6b3ebfa10b58d1a25961f7
W=$HOME/work; PY=$W/venv/bin/python; SRC=$W/sdb-gen7
mkdir -p "$W/runs" "$W/tools" "$W/publication"
curl -fsSL "https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/$SHA/ops/publish_test_run.py" -o "$W/tools/publish_test_run.py"
"$PY" -m py_compile "$W/tools/publish_test_run.py"
printf 'Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ\n' > "$W/runs/trailers.txt"
cat > "$W/runs/drive.sh" <<'SH'
#!/usr/bin/env bash
# drive.sh RUN BOARDS WORKERS: run the collector until BOARDS receipts exist, then STOP and let in-flight boards finish.
RUN=$1; N=$2; W=$3
cd "$HOME/work/sdb-gen7" || exit 1
"$HOME/work/venv/bin/python" -u ops/gen5_runtime.py --run "$RUN" --workers "$W" >> "$RUN.collector.log" 2>&1 &
pid=$!
echo "$(date -u +%FT%TZ) collector pid $pid, $W workers, STOP after $N boards"
while kill -0 "$pid" 2>/dev/null; do
  n=$(find "$RUN/receipts" -name '*.json' | wc -l)
  if [ "$n" -ge "$N" ] && [ ! -e "$RUN/STOP" ]; then touch "$RUN/STOP"; echo "$(date -u +%FT%TZ) $n boards: STOP written"; fi
  sleep 10
done
wait "$pid"; rc=$?
echo "$(date -u +%FT%TZ) collector exited with $rc after $(find "$RUN/receipts" -name '*.json' | wc -l) boards"
SH
chmod +x "$W/runs/drive.sh"
pgrep -f "ops/gen5_runtime.py" >/dev/null && { echo "a collector is already running here; nothing changed"; exit 1; }

case "$BOX" in
  azure1) RUN=$W/runs/g7s-vs-g6f-01; FIRST=0; LAST=5599; CAP=5600; WORKERS=8; SMOKE=$W/runs/smoke-01.json; COMMIT=1042db5 ;;
  azure2) FIRST=5627;  WORKERS=8 ;;
  azure3) FIRST=11254; WORKERS=10 ;;
  azure4) FIRST=16881; WORKERS=8 ;;
  *) echo "no block assigned to $BOX"; exit 1 ;;
esac

if [ "$BOX" = azure1 ]; then
  # Continue the run of 308 boards. Its STOP is the driver's own 300-board cap; the run drained with no failures.
  [ -z "$(ls "$RUN/failures")" ] || { echo "failures present in $RUN; not restarting"; exit 1; }
  echo "resuming $RUN at $(ls "$RUN/receipts" | wc -l) boards"
  rm -f "$RUN/STOP"
else
  RUN=$W/runs/pre7-7s-vs-6f-$BOX; COUNT=5627; LAST=$((FIRST + COUNT - 1)); CAP=$COUNT; SMOKE=$W/runs/smoke-$BOX.json; COMMIT=${SHA:0:7}
  [ "$(git -C "$W/capsule-gen7-capture" rev-parse HEAD)" = "$CAPSULE" ] || { echo "capsule is not at $CAPSULE; deal blocks would not line up"; exit 1; }
  [ -e "$RUN" ] && { echo "$RUN already exists; not overwriting"; exit 1; }
  git -C "$SRC" fetch -q --depth 1 origin "$SHA" && git -C "$SRC" checkout -q FETCH_HEAD
  echo "source now at $(git -C "$SRC" log -1 --format='%h %s' | cut -c1-90)"
  cd "$SRC"
  "$PY" - <<'PYEOF'
import json, os
p = json.load(open('configs/round7-candidate-phase1.json'))
p['launch_enabled'] = True
p['pending'] = []
p['roster'] = ['7s-32', '6-32']
p['pair_weights'] = {'7s-32~6-32': 1}
p['audit_references'] = {k: v for k, v in p['audit_references'].items() if k in p['roster']}
p['title'] = 'Pre-7 test: 7s-32 (tree path 0.5, 3 tricks) vs 6-32 on a test machine. Not an arena cohort'
json.dump(p, open(os.path.expanduser('~/work/runs/plan-7s-vs-6f.json'), 'w'), indent=1)
PYEOF
  "$PY" ops/prepare_gen7_alpha.py --source "$W/capsule-gen7-capture/recovery" --run "$RUN" --plan "$W/runs/plan-7s-vs-6f.json" --first "$FIRST" --count "$COUNT" | cut -c1-330
  "$PY" ops/smoke_gen7.py --run "$RUN" --out "$SMOKE" >/dev/null 2>"$W/runs/smoke-$BOX.err" && echo "preflight passed" || { echo "preflight FAILED:"; tail -5 "$W/runs/smoke-$BOX.err"; exit 1; }
fi

cat > "$W/runs/README-pre7.md" <<MD
# Pre-7 test data: $BOX

Gen 7 standard candidate (\`7s-32\`: policy v4, play weights, net tie-break, tree at tricks 3 to 6 with
the stake rule at \`path\` 0.5 and 3 tricks) against Gen 6 fast (\`6-32\`), played on test machine $BOX
from 12 November 2026 while the arena was still on Gen 6.

**A test run, not an arena cohort.** This branch is not a feed and its boards are not pooled into
arena scores.

- Run folder: \`$(basename "$RUN")/\` with \`manifest.json\`, \`plan.json\`, \`corpus.jsonl\`,
  \`source-indices.json\`, \`state.json\`, \`episodes/\`, \`receipts/\` and \`failures/\`.
- Deals: positions $FIRST to $LAST of the 22,508 unplayed deals of the
  \`arena-gen6-gen7-capture-feed\` capsule at \`8833c62\`. The other machines play other blocks.
- Workers: $WORKERS, each held to one thread. Source commit: \`$COMMIT\`.
- Sibling branches: \`transfer/pre7-test-azure1-20261112\` to \`transfer/pre7-test-azure4-20261112\`.
- Guide, settings and limits: \`docs/pre7_test_2026-11-12.md\` on \`feature/gen7-prepare-slice-20261112\`.

Written by \`ops/publish_test_run.py\` every ten minutes while the run is live.
MD

CAPS="--setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 --setenv=MKL_NUM_THREADS=1 --setenv=TF_NUM_INTRAOP_THREADS=1 --setenv=TF_NUM_INTEROP_THREADS=1 --setenv=TF_CPP_MIN_LOG_LEVEL=3"
sudo systemd-run --quiet --unit=pre7-match --uid="$(id -un)" --setenv=HOME="$HOME" $CAPS \
  --working-directory="$SRC" -- "$W/runs/drive.sh" "$RUN" "$CAP" "$WORKERS"
EXTRA=(); [ -e "$SMOKE" ] && EXTRA=(--extra "$SMOKE")
PLAN=(); [ -e "$W/runs/plan-7s-vs-6f.json" ] && PLAN=(--plan "$W/runs/plan-7s-vs-6f.json")
sudo systemd-run --quiet --unit=pre7-publish --uid="$(id -un)" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 \
  --working-directory="$W" -- "$PY" -u "$W/tools/publish_test_run.py" --run "$RUN" --branch "transfer/pre7-test-$BOX-20261112" \
  --checkout "$W/publication/pre7-test" "${PLAN[@]}" "${EXTRA[@]}" --readme "$W/runs/README-pre7.md" \
  --ssh-key "$HOME/.ssh/boxctl_github" --trailers-file "$W/runs/trailers.txt" --every 600
sleep 75
echo "match unit: $(systemctl is-active pre7-match); publisher unit: $(systemctl is-active pre7-publish)"
journalctl -u pre7-match --no-pager -n 2 -o cat | cut -c1-160
journalctl -u pre7-publish --no-pager -n 3 -o cat | cut -c1-200
echo "boards: $(ls "$RUN/receipts" | wc -l); $(uptime | sed 's/.*load/load/')"
