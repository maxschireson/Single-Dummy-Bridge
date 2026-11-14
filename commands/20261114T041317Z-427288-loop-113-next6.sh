# boxctl: timeout=300
# boxctl: timeout=300
# loop session (Max, 03:45 UTC on 14 November: "we need to randomize ourselves a bit too ... maybe we can spend a quarter imp"):
# once the blind matches (unit loop-rungs2) have ended on azure6, the source moves to 38b19d2 and rungs.sh plays
# jobs-azure6-mix.txt (the collection pauses for it and restarts after). Launched as the unit loop-rungs3, so this returns at once.
set -euo pipefail
W=$HOME/work/loop; S=$W/src
cat > "$W/after-next3.sh" <<EOS
#!/usr/bin/env bash
while [ "\$(systemctl is-active loop-rungs)" = active ] || [ "\$(systemctl is-active loop-rungs2)" = active ]; do sleep 30; done; sleep 45
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" checkout -q 38b19d29a7d9933ba2716c545baf1f6044122edc
bash "$S/training/rollout-loop-20261113/rungs.sh" jobs-azure6-mix.txt azure6
EOS
sudo systemctl reset-failed loop-rungs3 2>/dev/null || true
sudo systemd-run --unit=loop-rungs3 --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/after-next3.sh"
sleep 5; echo "loop-rungs: $(systemctl is-active loop-rungs || true); loop-rungs2: $(systemctl is-active loop-rungs2 || true); loop-rungs3: $(systemctl is-active loop-rungs3 || true)"; tail -n 2 "$W/runs.log" | cut -c1-170
"$W/venv/bin/python" - <<'PY'
import json, glob, os
for run in ('h3-pt', 'l3-pu'):
    f = os.path.expanduser(f'~/work/loop/runs/{run}/results.jsonl')
    if not os.path.exists(f): print(run, 'not started'); continue
    v = [json.loads(l)['common'] for l in open(f) if l.strip()]
    n = len(v); m = sum(v) / max(n, 1); se = (sum((x - m) ** 2 for x in v) / max(n - 1, 1) / max(n, 1)) ** .5
    print(run, 'boards %d: %+.2f +- %.2f IMPs a board for the first-named bot' % (n, m, se))
PY
date -u +%FT%TZ
