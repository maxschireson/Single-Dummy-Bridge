# boxctl: timeout=180
# Gen 7.1 on this box (Max, 12 Nov 05:42 UTC): build feature/gen7-selfplay-20261112 at 9f5ec19, run its tests, prepare the cohort of
# 7.1 against 7.0 and against Gen 6 from this box's stopped Gen 7.0 self-play cohort (11 boards played), preflight, six trial boards,
# publish. Background unit gen71-trial; progress in ~/work/gen71/trial.log. The BEN lanes keep running.
set -euo pipefail
W=$HOME/work; S=$W/gen71; mkdir -p "$S"
printf 'BOX=%s\nOLD=%s\n' "$BOXCTL_BOX" "$W/runs/gen7-phase1-selfplay-capture-$BOXCTL_BOX" > "$S/gen71.env"
cat > "$S/gen71.sh" <<'EOF_GEN71_SH'
#!/usr/bin/env bash
# Gen 7.1 on this box (Max, 12 November 2026, 05:42 UTC): 71s-32 (Gen 7 standard with policy net v4.1) against
# 7s-32, two boards in three, and against Gen 6 fast, one in three. The cohort takes over the deals that a drained
# Gen 7 cohort of this box (OLD in gen71.env) had not played. Source branch feature/gen7-selfplay-20261112.
#
#   gen71.sh build | tests | prepare | preflight | records | units | trial N | publish | start WORKERS | status
set -euo pipefail
W=$HOME/work; PY=$W/venv/bin/python; SRC=$W/sdb-gen71; S=$W/gen71
COMMIT=9f5ec19498e7e20e9f610ed93d896880a17cbcc9
. "$S/gen71.env"      # BOX, OLD (the drained cohort whose unplayed deals this one takes over)
RUN=$W/runs/gen71-compare-$BOX; PUB=$W/publication/gen71-compare-$BOX; BRANCH=arena-gen7-1-compare-$BOX-feed
PLAN=configs/round71-compare.json
U=$(id -un)
CAPS="OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TF_NUM_INTRAOP_THREADS=1 TF_NUM_INTEROP_THREADS=1 TF_CPP_MIN_LOG_LEVEL=3"
SSH="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
REMOTE=git@github.com:maxschireson/Single-Dummy-Bridge.git
say() { echo "$(date -u +%T) $*"; }

cmd_build() {
  if [ ! -d "$SRC/.git" ]; then git init -q "$SRC" && git -C "$SRC" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; fi
  git -C "$SRC" fetch -q --depth 1 origin "$COMMIT" && git -C "$SRC" checkout -q FETCH_HEAD || { say "could not check out $COMMIT"; exit 1; }
  say "checkout: $(git -C "$SRC" log -1 --format='%H %s' | cut -c1-110)"
  cd "$SRC"
  for r in models/*/*/restore*.py; do
    (cd "$(dirname "$r")" && "$PY" "$(basename "$r")" >/dev/null 2>/tmp/restore.err) || say "FAILED $r: $(tail -1 /tmp/restore.err)"
  done
  "$PY" scripts/build_dds.py >/dev/null 2>&1 || true
  [ -s bridge_harness/libbridge_dds.so ] || { say "DDS library was not built"; exit 1; }
  say "policy v4 $(sha256sum models/cardplay/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz | cut -c1-16), v4.1 $(sha256sum models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz | cut -c1-16); dds library $(sha256sum bridge_harness/libbridge_dds.so | cut -c1-16) (phase 1 checkout: $(sha256sum $W/sdb-gen7-arena/bridge_harness/libbridge_dds.so | cut -c1-16))"
}

cmd_tests() {
  cd "$SRC"; local start; start=$(date +%s)
  local out bad=
  for pattern in "test_gen7*.py" "test_gap_forks.py" "test_gen[56]*.py"; do
    out=$(env $CAPS "$PY" -m unittest discover -s tests -p "$pattern" 2>&1 | grep -E "^(Ran|OK|FAILED|ERROR:|FAIL:)" | tr '\n' ' ' | cut -c1-600) || true
    say "tests $pattern: $out"
    case "$pattern:$out" in "test_gen[56]*.py:"*) ;; *" OK"*) ;; *) bad=1 ;; esac
  done
  say "tests took $(( $(date +%s) - start ))s"
  [ -z "$bad" ] || { say "the Gen 7 or gap fork tests did not pass"; exit 1; }
}

cmd_prepare() {
  [ "$(git -C "$SRC" rev-parse HEAD)" = "$COMMIT" ] || { say "source is not at $COMMIT"; exit 1; }
  [ -e "$RUN" ] && { say "$RUN already exists; not overwriting"; exit 1; }
  [ -e "$PUB" ] && { say "$PUB already exists; not overwriting"; exit 1; }
  if GIT_SSH_COMMAND="$SSH" git ls-remote --exit-code --heads "$REMOTE" "$BRANCH" >/dev/null 2>&1; then say "branch $BRANCH already exists on GitHub"; exit 1; fi
  # The source run is a Gen 7 cohort of this box. It has to be finished: stopped, collectors gone, records published.
  [ -e "$OLD/STOP" ] || { say "$OLD has no STOP file"; exit 1; }
  for unit in arena-gen7 arena-gen71 arena-gen71; do
    [ "$(systemctl is-active $unit 2>/dev/null)" = active ] && { say "the collector $unit is still running"; exit 1; }
  done
  [ -z "$(ls "$OLD/failures" 2>/dev/null)" ] || { say "the source cohort has failure records"; exit 1; }
  local played published
  played=$(ls "$OLD/receipts" | wc -l)
  published=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$OLD/publisher-status.json")
  [ "$played" = "$published" ] || { say "the source cohort has published $published of $played boards; publish the rest first"; exit 1; }
  [ -e "$OLD/WATCHDOG_STOP" ] || echo "Finished for good on $(date -u +%FT%TZ). The deals this cohort had not played go to $(basename "$RUN"). No watchdog ran on this box." > "$OLD/WATCHDOG_STOP"
  cd "$SRC"
  "$PY" ops/prepare_gen7_alpha.py --source "$OLD" --run "$RUN" --plan "$PLAN" > "$S/prepare.json"
  "$PY" - "$S/prepare.json" "$OLD" "$RUN" "$played" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1])); old = json.load(open(sys.argv[2] + '/manifest.json')); m = json.load(open(sys.argv[3] + '/manifest.json')); played = int(sys.argv[4])
tree = d['gen7']['71s-32']['tree'][0]
assert d['gen7']['71s-32'] == d['gen7']['7s-32'], 'the two bots differ in more than the net'
assert d['allocation'] == {'71s-32~6-32': 1, '71s-32~7s-32': 2}, d['allocation']
assert (tree['root_margin'], tree['trust'], tree['path'], tree['tricks']) == (0.25, 0.3, 0.5, 3), 'not the authorized tree settings'
assert m['bots']['7s-32'] == old['bots']['7s-32'], '7s-32 is not the phase 1 bot'
a, b = m['bots']['7s-32'], m['bots']['71s-32']
assert {k for k in a if a[k] != b.get(k)} == {'id', 'identity', 'gen7_policy', 'artifact_sha256'}, 'the two bots differ in more than the net'
assert b['artifact_sha256']['gen7_policy'] == 'cb3fcfd5c55873735ee22ea5e7ba04606794bed38d261fdf3f1b3a4af5c9fbed' and b['gen7_policy'].endswith('gen7_policy_v41.npz')
assert m['target'] == old['target'] - played and m['source_generation'] == old['identity'] and m['source_completed'] == played
print(f"cohort {d['identity'][:12]}: {d['target']} deals taken over from cohort {old['identity'][:12]} ({played} of its {old['target']} were played); pairs {d['allocation']}; "
      f"7s-32 identity {m['bots']['7s-32']['identity'][:12]} as in phase 1; 71s-32 identity {b['identity'][:12]}, differing from 7s-32 in the policy release only; audit {m['audit']}; gap forks {m.get('gap_fork')}")
PYEOF
}

cmd_preflight() {
  cd "$SRC"; local start; start=$(date +%s)
  if ! env $CAPS "$PY" ops/smoke_gen7.py --run "$RUN" --out "$RUN/preflight.json" --deals 2 > "$S/preflight.log" 2>&1; then
    say "preflight FAILED"; grep -v -E "absl|oneDNN|cpu_feature|AVX|^WARNING" "$S/preflight.log" | tail -14 | cut -c1-300; exit 1
  fi
  "$PY" - "$RUN/preflight.json" "$(( $(date +%s) - start ))" <<'PYEOF'
import json, sys
r = json.load(open(sys.argv[1])); t = r['tree']
print(f"preflight passed in {sys.argv[2]}s:")
for d in r['deals']:
    print(f"   deal {d['index']} {d['pair']}: {round(d['seconds'])}s, root tables {d['root_tables']}, tables with forks {d['tables']}, IMPs {d['imps']}, searched decisions {d['decisions']}, "
          f"in the tree's tricks {d['in_a_stage']}, tree consulted {d['consulted']}, moved {d['moved']}, tree forks {d['tree_forks']}, gap forks {d.get('gap_forks')} on {d.get('gap_enabled_roots')} tables")
print('   tree in all:', {k: (round(v, 2) if isinstance(v, float) else v) for k, v in t.items()})
PYEOF
}

cmd_records() {
  cp "$SRC/$PLAN" "$RUN/plan.json"
  "$PY" -m pip freeze 2>/dev/null > "$RUN/runtime-requirements.txt"
  env TF_CPP_MIN_LOG_LEVEL=3 "$PY" - "$RUN" "$BOX" "$COMMIT" "$BRANCH" "$(basename "$OLD")" 2>/dev/null <<'PYEOF'
import json, os, platform, sys, time
run, box, commit, branch, old = sys.argv[1:6]
import numpy, scipy, tensorflow as tf
cpu = next((l.split(':', 1)[1].strip() for l in open('/proc/cpuinfo') if l.lower().startswith('model name')), None)
json.dump(dict(host=box, machine='Azure Standard_F8as_v6, 8 vCPUs, 32 GB', cpu=cpu, os=platform.platform(), python=sys.version.split()[0],
    packages=dict(tensorflow=tf.__version__, numpy=numpy.__version__, scipy=scipy.__version__),
    source_repository='https://github.com/maxschireson/Single-Dummy-Bridge', source_branch='feature/gen7-selfplay-20261112', source_commit=commit, generation='Gen 7.1: 71s-32 is 7s-32 with policy net v4.1',
    source_run=f"this machine's drained cohort {old}: the deals it had not played",
    capture='tie audits, tree audits, gap forks and the guess-size fields (this source has the capture port merged)',
    plan='configs/round71-compare.json (plan.json beside this file)', threads='one BLAS, OpenMP and TensorFlow thread a worker',
    publication_branch=branch, supervision='systemd units arena-gen71 and arena-gen71-publish; no BEN pair in this cohort',
    operator='Claude session https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ, through the boxctl agent (docs/boxctl.md)'),
    open(os.path.join(run, 'environment.json'), 'w'), indent=1)
json.dump(dict(launched_epoch=time.time(),
    authority="Max, 12 November 2026, 05:42 UTC: push 7.1 from 06:00 UTC unless revoked; replace the 7.0 self play with 7.0/7.1 matches for at least 1000 boards / until 7.1 establishes a 95% CI lead, then 7.1 self play; all other matches replace 7 with 7.1",
    notice='docs/gen71_2026-11-12.md on feature/gen7-selfplay-20261112', host=box,
    steps='prepare from the drained cohort, preflight with ops/smoke_gen7.py, a short trial with two workers, then the collector under systemd'),
    open(os.path.join(run, 'launch.json'), 'w'), indent=1)
PYEOF
  mkdir -p "$PUB" && git -C "$PUB" init -q && git -C "$PUB" checkout -q --orphan "$BRANCH"
  git -C "$PUB" remote add origin "$REMOTE"
  git -C "$PUB" config core.sshCommand "$SSH"
  git -C "$PUB" config user.name "Claude"; git -C "$PUB" config user.email "noreply@anthropic.com"
  cat > "$PUB/.git/hooks/commit-msg" <<'HOOK'
#!/bin/sh
grep -q "^Claude-Session:" "$1" || printf '\nCo-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ\n' >> "$1"
HOOK
  chmod +x "$PUB/.git/hooks/commit-msg"
  say "records written; publication checkout on $BRANCH"
}

cmd_units() {
  [ -e "$S/workers.env" ] || echo "WORKERS=2" > "$S/workers.env"
  sudo tee /etc/systemd/system/arena-gen71.service >/dev/null <<UNIT
[Unit]
Description=Gen 7.1 collector: 7.1 against 7.0 and against Gen 6 fast
StartLimitIntervalSec=900
StartLimitBurst=3

[Service]
User=$U
WorkingDirectory=$SRC
EnvironmentFile=$S/workers.env
Environment=HOME=$HOME PYTHONUNBUFFERED=1 $CAPS
ExecStart=$PY -u ops/gen5_runtime.py --run $RUN --workers \${WORKERS}
StandardOutput=append:$S/collector.log
StandardError=append:$S/collector.log
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
UNIT
  sudo tee /etc/systemd/system/arena-gen71-publish.service >/dev/null <<UNIT
[Unit]
Description=Gen 7.1 compare feed publisher
After=network-online.target
Wants=network-online.target

[Service]
User=$U
WorkingDirectory=$SRC
Environment=HOME=$HOME PYTHONUNBUFFERED=1 $CAPS
ExecStart=$PY -u ops/publish_gen5.py --run $RUN --publication $PUB
StandardOutput=append:$S/publisher.log
StandardError=append:$S/publisher.log
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
UNIT
  sudo systemctl daemon-reload
  say "units written"
}

boards() { ls "$RUN/receipts" 2>/dev/null | wc -l; }

cmd_trial() {       # a few real boards with two workers, then a clean stop
  local want=$1 start; start=$(date +%s)
  echo "WORKERS=2" > "$S/workers.env"; rm -f "$RUN/STOP"
  sudo systemctl start arena-gen71
  while [ "$(boards)" -lt "$want" ] && [ $(( $(date +%s) - start )) -lt 2400 ] && [ "$(systemctl is-active arena-gen71)" = active ]; do sleep 10; done
  touch "$RUN/STOP"
  for i in $(seq 1 120); do [ "$(systemctl is-active arena-gen71)" = active ] || break; sleep 10; done
  say "trial: $(boards) boards in $(( $(date +%s) - start ))s with two workers; collector now $(systemctl is-active arena-gen71); failures: $(ls "$RUN/failures" | tr '\n' ' ')"
  [ -z "$(ls "$RUN/failures")" ] || { for f in "$RUN"/failures/*.json; do cut -c1-600 "$f"; echo; done; tail -5 "$S/collector.log" | cut -c1-300; exit 1; }
}

cmd_publish() {     # one publication, then the publisher stays up
  cd "$SRC"
  env $CAPS "$PY" ops/publish_gen5.py --run "$RUN" --publication "$PUB" --once > "$S/publish-once.log" 2>&1 || { say "publication FAILED"; tail -8 "$S/publish-once.log" | cut -c1-300; exit 1; }
  say "published: $(git -C "$PUB" log -1 --format='%h %s' | cut -c1-90) on $BRANCH"
  sudo systemctl enable --now arena-gen71-publish >/dev/null 2>&1 || true
}

cmd_start() {       # the collector at full strength
  echo "WORKERS=$1" > "$S/workers.env"; rm -f "$RUN/STOP"
  sudo systemctl enable --now arena-gen71 >/dev/null 2>&1 || true
  sudo systemctl enable --now arena-gen71-publish >/dev/null 2>&1 || true
  say "collector $(systemctl is-active arena-gen71) with $1 workers, publisher $(systemctl is-active arena-gen71-publish), feed $BRANCH"
}

cmd_status() {
  "$PY" - "$RUN" <<'PYEOF'
import glob, gzip, json, os, subprocess, sys, time
run = sys.argv[1]; now = time.time()
unit = lambda n: subprocess.run(['systemctl', 'is-active', n], capture_output=True, text=True).stdout.strip()
m = json.load(open(run + '/manifest.json'))
rs = [json.load(open(p)) for p in glob.glob(run + '/receipts/*.json')]
try: pub = json.load(open(run + '/publisher-status.json')); pub = f"{pub.get('status')} {pub.get('completed')} ({round(now - pub['epoch'])}s ago)"
except Exception: pub = 'no status yet'
print(f"cohort {m['identity'][:12]}: {len(rs)} of {m['target']} boards; last 10 min {sum(r['completed_epoch'] > now - 600 for r in rs)}; collector {unit('arena-gen71')}, "
      f"publisher {unit('arena-gen71-publish')} [{pub}]; STOP {os.path.exists(run + '/STOP')}; failures {sorted(os.listdir(run + '/failures'))}")
by = {}
for r in rs:
    by.setdefault(r['pair'], []).append(r)
for pair, rows in sorted(by.items()):
    x = [r['imps'] for r in rows if r['imps'] is not None]
    cpu = []; forks = []; tables = []; gaps = []
    for r in rows[-40:]:
        d = json.load(gzip.open(f"{run}/episodes/{r['index']:06d}.json.gz", 'rt'))
        cpu.append(d['base_cpu'] + d['branch_cpu'] + d.get('gap_cpu', 0)); forks.append(sum(len(e.get('audits', [])) for e in d['unique_tables'].values()))
        gaps.append(d.get('gap_fork_count', 0)); tables.append(r['tables'])
    mean = lambda v: round(sum(v) / len(v), 1) if v else None
    print(f"   {pair}: {len(rows)} boards, IMPs {('%+d' % sum(x)) if x else 'none (training only)'}, with a score {len(x)}; last {len(cpu)}: cpu-s a board {mean(cpu)}, tables a board {mean(tables)}, "
          f"audit forks a board {mean(forks)}, gap forks a board {mean(gaps)}")
PYEOF
}

cmd=$1; shift
"cmd_$cmd" "$@"
EOF_GEN71_SH
cat > "$S/trial.sh" <<'EOF_TRIAL_SH'
#!/usr/bin/env bash
# Build the Gen 7.1 source, test it, prepare the 7.1-against-7.0 cohort from this box's stopped self-play cohort, preflight,
# play six boards with two workers, publish once, and leave the cohort stopped.
set -uo pipefail
S=$HOME/work/gen71
for step in build tests prepare preflight records units "trial 6" publish status; do
  echo "$(date -u +%T) == $step"
  bash "$S/gen71.sh" $step || { echo "$(date -u +%T) STOPPED at: $step"; exit 1; }
done
echo "$(date -u +%T) DONE"
EOF_TRIAL_SH
chmod +x "$S/gen71.sh" "$S/trial.sh"
systemctl is-active --quiet gen71-trial && { echo "already running"; exit 0; }
sudo systemctl reset-failed gen71-trial 2>/dev/null || true
sudo systemd-run --quiet --unit=gen71-trial --uid="$(id -un)" --setenv=HOME="$HOME" \
  --property=StandardOutput=append:"$S/trial.log" --property=StandardError=append:"$S/trial.log" -- "$S/trial.sh"
sleep 30; echo "gen71-trial: $(systemctl is-active gen71-trial)"; tail -5 "$S/trial.log" | cut -c1-300
