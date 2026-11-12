# boxctl: timeout=120
# Gen 7.1 on this box, effective 06:00 UTC (Max, 05:42 and 05:54 UTC): azure2 plays 7.1 against 7.0 on every board. The eight Gen 7.0
# BEN (16) lanes are finished and published (nothing deleted) and their servers stopped; the box's first Gen 7.1 cohort (1:2 mix) is
# closed after its trial and the 100% cohort takes over its unplayed deals and runs with eight workers.
# Background unit go71b; progress in ~/work/gen71/go71b.log.
set -euo pipefail
W=$HOME/work; L=$W/lanes; S=$W/gen71
cat > "$L/drain70.sh" <<'EOF_DRAIN70_SH'
#!/usr/bin/env bash
# Finish this box's eight Gen 7.0 BEN lanes for good: switch the memory supervisor off, STOP every lane, wait for the boards in
# hand, wait until every feed carries every board, then stop the publishers. Nothing is deleted.
set -uo pipefail
W=$HOME/work; L=$W/lanes; PY=$W/venv/bin/python; . "$L/role.env"
say() { echo "$(date -u +%T) $*"; }
old() { echo "$W/runs/gen7-phase1-$BOX-$LABEL-$1"; }
LANES="1 2 3 4 5 6 7 8"
touch "$L/RECYCLE_OFF"
for i in $(seq 1 120); do ls "$L"/*.recycling >/dev/null 2>&1 || break; sleep 5; done
sudo systemctl disable --now lane-recycle >/dev/null 2>&1
for n in $LANES; do touch "$(old $n)/STOP"; done
a=8
for i in $(seq 1 240); do a=0; for n in $LANES; do [ "$(systemctl is-active arena-ben@$n)" = active ] && a=$((a+1)); done; [ "$a" -eq 0 ] && break; sleep 5; done
[ "$a" -eq 0 ] || { say "collectors still running after 20 minutes: $a"; exit 1; }
for n in $LANES; do
  [ -z "$(ls "$(old $n)/failures")" ] || { say "lane $n has a failure record: $(ls "$(old $n)/failures" | tr '\n' ' ')"; exit 1; }
  sudo systemctl disable "arena-ben@$n" >/dev/null 2>&1
done
behind=8
for i in $(seq 1 60); do
  behind=0
  for n in $LANES; do
    p=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$(old $n)/publisher-status.json" 2>/dev/null); r=$(ls "$(old $n)/receipts" | wc -l)
    [ "$p" = "$r" ] || behind=$((behind+1))
  done
  [ "$behind" -eq 0 ] && break; sleep 10
done
[ "$behind" -eq 0 ] || { say "feeds still behind after 10 minutes: $behind"; exit 1; }
for n in $LANES; do touch "$(old $n)/PUBLISH_STOP"; done
for i in $(seq 1 30); do a=0; for n in $LANES; do [ "$(systemctl is-active arena-ben-publish@$n)" = active ] && a=$((a+1)); done; [ "$a" -eq 0 ] && break; sleep 5; done
for n in $LANES; do sudo systemctl disable --now "arena-ben-publish@$n" >/dev/null 2>&1; done
total=0; for n in $LANES; do total=$((total + $(ls "$(old $n)/receipts" | wc -l))); done
say "the eight Gen 7.0 lanes against $BENNAME are finished: $total boards, every one published, no failures"
EOF_DRAIN70_SH
cat > "$S/gen71b.sh" <<'EOF_GEN71B_SH'
#!/usr/bin/env bash
# Gen 7.1 against Gen 7.0 on this box, every board (Max, 12 November 2026, 05:54 UTC: "We can switch azure 2 to 100%
# 7.1 vs 7.0; 7 is clearly a big step vs 6."): 71s-32 (Gen 7 standard with policy net v4.1) against 7s-32. The cohort
# takes over the deals that the box's first Gen 7.1 cohort (OLD in gen71b.env) had not played.
#
#   gen71b.sh plan | prepare | preflight | records | units | start WORKERS | status   (build and tests: gen71.sh)
set -euo pipefail
W=$HOME/work; PY=$W/venv/bin/python; SRC=$W/sdb-gen71; S=$W/gen71
COMMIT=9f5ec19498e7e20e9f610ed93d896880a17cbcc9
. "$S/gen71b.env"      # BOX, OLD (the drained cohort whose unplayed deals this one takes over)
RUN=$W/runs/gen71-vs70-$BOX; PUB=$W/publication/gen71-vs70-$BOX; BRANCH=arena-gen7-1-vs70-$BOX-feed
PLAN=$S/plan-vs70.json
U=$(id -un)
CAPS="OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TF_NUM_INTRAOP_THREADS=1 TF_NUM_INTEROP_THREADS=1 TF_CPP_MIN_LOG_LEVEL=3"
SSH="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
REMOTE=git@github.com:maxschireson/Single-Dummy-Bridge.git
say() { echo "$(date -u +%T) $*"; }

cmd_plan() {
  [ "$(git -C "$SRC" rev-parse HEAD)" = "$COMMIT" ] || { say "source is not at $COMMIT"; exit 1; }
  "$PY" - "$SRC/configs/round71-compare.json" "$PLAN" "$BOX" <<'PYEOF'
import json, sys
src, dst, box = sys.argv[1:4]
p = json.load(open(src))
assert p['launch_enabled'] is True and not p['pending'], 'the Gen 7.1 comparison plan is not open'
pair = '71s-32~7s-32'
assert pair in p['pair_weights'], pair
p['roster'] = ['71s-32', '7s-32']
p['pair_weights'] = {pair: 1}
p['title'] = f'Gen 7.1 · standard with policy v4.1 against Gen 7 standard, every board, on {box}'
p['notes'] = list(p.get('notes', [])) + [
    "This copy of configs/round71-compare.json keeps one of its two pairs, 71s-32~7s-32: Max, 12 November 2026, 05:54 UTC, \"We can switch azure 2 to 100% 7.1 vs 7.0; "
    "7 is clearly a big step vs 6.\" Only the roster, the pair weights, the title and this note differ from that file."]
json.dump(p, open(dst, 'w'), indent=1)
print('plan:', p['title'], '| pairs', p['pair_weights'], '| bots', sorted(p['gen7_bots']), '| artifacts', sorted(p['artifacts']))
PYEOF
}

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
  "$PY" ops/prepare_gen7_alpha.py --source "$OLD" --run "$RUN" --plan "$PLAN" > "$S/prepare-vs70.json"
  "$PY" - "$S/prepare-vs70.json" "$OLD" "$RUN" "$played" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1])); old = json.load(open(sys.argv[2] + '/manifest.json')); m = json.load(open(sys.argv[3] + '/manifest.json')); played = int(sys.argv[4])
tree = d['gen7']['71s-32']['tree'][0]
assert d['gen7']['71s-32'] == d['gen7']['7s-32'], 'the two bots differ in more than the net'
assert d['allocation'] == {'71s-32~7s-32': 1}, d['allocation']
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
  if ! env $CAPS "$PY" ops/smoke_gen7.py --run "$RUN" --out "$RUN/preflight.json" --deals 2 > "$S/preflight-vs70.log" 2>&1; then
    say "preflight FAILED"; grep -v -E "absl|oneDNN|cpu_feature|AVX|^WARNING" "$S/preflight-vs70.log" | tail -14 | cut -c1-300; exit 1
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
  cp "$PLAN" "$RUN/plan.json"
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
    plan='configs/round71-compare.json reduced to the pair 71s-32~7s-32 (plan.json beside this file)', threads='one BLAS, OpenMP and TensorFlow thread a worker',
    publication_branch=branch, supervision='systemd units arena-gen71 and arena-gen71-publish; no BEN pair in this cohort',
    operator='Claude session https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ, through the boxctl agent (docs/boxctl.md)'),
    open(os.path.join(run, 'environment.json'), 'w'), indent=1)
json.dump(dict(launched_epoch=time.time(),
    authority="Max, 12 November 2026, 05:42 UTC: push 7.1 from 06:00 UTC unless revoked; replace the 7.0 self play with 7.0/7.1 matches for at least 1000 boards / until 7.1 establishes a 95% CI lead. 05:54 UTC: 'We can switch azure 2 to 100% 7.1 vs 7.0; 7 is clearly a big step vs 6.'",
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
Description=Gen 7.1 collector: 7.1 against 7.0
StartLimitIntervalSec=900
StartLimitBurst=3

[Service]
User=$U
WorkingDirectory=$SRC
EnvironmentFile=$S/workers.env
Environment=HOME=$HOME PYTHONUNBUFFERED=1 $CAPS
ExecStart=$PY -u ops/gen5_runtime.py --run $RUN --workers \${WORKERS}
StandardOutput=append:$S/collector-vs70.log
StandardError=append:$S/collector-vs70.log
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
UNIT
  sudo tee /etc/systemd/system/arena-gen71-publish.service >/dev/null <<UNIT
[Unit]
Description=Gen 7.1 against 7.0 feed publisher
After=network-online.target
Wants=network-online.target

[Service]
User=$U
WorkingDirectory=$SRC
Environment=HOME=$HOME PYTHONUNBUFFERED=1 $CAPS
ExecStart=$PY -u ops/publish_gen5.py --run $RUN --publication $PUB
StandardOutput=append:$S/publisher-vs70.log
StandardError=append:$S/publisher-vs70.log
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
  [ -z "$(ls "$RUN/failures")" ] || { for f in "$RUN"/failures/*.json; do cut -c1-600 "$f"; echo; done; tail -5 "$S/collector-vs70.log" | cut -c1-300; exit 1; }
}

cmd_publish() {     # one publication, then the publisher stays up
  cd "$SRC"
  env $CAPS "$PY" ops/publish_gen5.py --run "$RUN" --publication "$PUB" --once > "$S/publish-once.log" 2>&1 || { say "publication FAILED"; tail -8 "$S/publish-once.log" | cut -c1-300; exit 1; }
  say "published: $(git -C "$PUB" log -1 --format='%h %s' | cut -c1-90) on $BRANCH"
  sudo systemctl enable --now arena-gen71-publish >/dev/null 2>&1 || true
}

cmd_start() {       # the collector at full strength
  # Eight new workers opening a solver cache that does not exist yet can collide on it (seen on this box on 12 November:
  # "database is locked"). Create it first with the statements bridge_harness/dds_cache.py itself runs.
  [ -e "$RUN/dds-cache.sqlite" ] || "$PY" - "$RUN/dds-cache.sqlite" <<'PYEOF'
import sqlite3, sys
db = sqlite3.connect(sys.argv[1], timeout=60)
db.execute('PRAGMA journal_mode=WAL')
db.execute('PRAGMA synchronous=FULL')
db.execute('CREATE TABLE IF NOT EXISTS positions (solver BLOB NOT NULL, position BLOB NOT NULL, scores BLOB NOT NULL,PRIMARY KEY(solver,position)) WITHOUT ROWID')
db.commit(); db.close()
PYEOF
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
EOF_GEN71B_SH
cat > "$S/go71b.sh" <<'EOF_GO71B_SH'
#!/usr/bin/env bash
# azure2 goes to Gen 7.1 against Gen 7.0 on every board (Max, 05:54 UTC). In parallel: finish the eight Gen 7.0 BEN (16) lanes and
# stop their servers; close the box's first Gen 7.1 cohort (the 1:2 mix, after its trial) and prepare the 100% cohort from its
# unplayed deals. Then run that with eight workers.
set -uo pipefail
W=$HOME/work; L=$W/lanes; S=$W/gen71; PY=$W/venv/bin/python
. "$S/gen71.env"
say() { echo "$(date -u +%T) $*"; }
F=$W/runs/gen71-compare-$BOX
say "== finish the 7.0 BEN lanes (in the background)"
( bash "$L/drain70.sh" > "$S/drain70.out" 2>&1; echo $? > "$S/drain70.rc" ) &
say "== wait for the first cohort's trial"
for i in $(seq 1 240); do [ "$(systemctl is-active gen71-trial)" = active ] || break; sleep 5; done
tail -5 "$S/trial.log" | cut -c1-400
grep -q " DONE$" "$S/trial.log" || { say "the trial did not finish cleanly; stopping here"; wait; exit 1; }
say "== close the first cohort"
for i in $(seq 1 60); do
  p=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$F/publisher-status.json" 2>/dev/null); r=$(ls "$F/receipts" | wc -l)
  [ "$p" = "$r" ] && break; sleep 10
done
touch "$F/PUBLISH_STOP"
for i in $(seq 1 30); do [ "$(systemctl is-active arena-gen71-publish)" = active ] || break; sleep 5; done
sudo systemctl disable --now arena-gen71-publish >/dev/null 2>&1; sudo systemctl disable arena-gen71 >/dev/null 2>&1
say "first cohort: $(ls "$F/receipts" | wc -l) boards, published $p; pairs $("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['by_pair'])" "$F/state.json")"
printf 'BOX=%s\nOLD=%s\n' "$BOX" "$F" > "$S/gen71b.env"
for step in plan prepare preflight records units; do
  say "== $step"
  bash "$S/gen71b.sh" $step || { say "STOPPED at: $step"; wait; exit 1; }
done
wait
cat "$S/drain70.out" | cut -c1-300
[ "$(cat "$S/drain70.rc")" = 0 ] || { say "the BEN lanes did not finish cleanly; the comparison cohort is ready but not started"; exit 1; }
for n in 1 2 3 4 5 6 7 8; do sudo systemctl disable --now "ben-server@$n" >/dev/null 2>&1; sudo systemctl disable --now "benlane-netns@$n" >/dev/null 2>&1; done
say "BEN servers stopped; $(free -m | awk 'NR==2{print "available " $7 " MB"}')"
say "== start with eight workers"
bash "$S/gen71b.sh" start 8 || exit 1
sleep 300
bash "$S/gen71b.sh" status
say "$(free -m | awk 'NR==2{print "available " $7 " MB"}'); worker processes: $(ps -eo args --no-headers | grep -c '[m]ultiprocessing.spawn')"
grep -c "database is locked" "$S/collector-vs70.log" | sed 's/^/database-is-locked lines in the collector log: /'
say DONE
EOF_GO71B_SH
chmod +x "$L/drain70.sh" "$S/gen71b.sh" "$S/go71b.sh"
systemctl is-active --quiet go71b && { echo "already running"; exit 0; }
sudo systemctl reset-failed go71b 2>/dev/null || true
sudo systemd-run --quiet --unit=go71b --uid="$(id -un)" --setenv=HOME="$HOME" \
  --property=StandardOutput=append:"$S/go71b.log" --property=StandardError=append:"$S/go71b.log" -- "$S/go71b.sh"
sleep 20; echo "go71b: $(systemctl is-active go71b)"; tail -4 "$S/go71b.log" | cut -c1-240
