# boxctl: timeout=60
# Prepare this box's next Gen 8 cohort while the current one plays (the Azure pools run out tonight; board, 18:02 UTC),
# then arm next8, which starts it when the current cohort has played and published every deal. Unit prepnext8; log ~/work/gen8/prepnext8.log.
set -euo pipefail
S=$HOME/work/gen8
cat > "$S/gen8n.sh" <<'EOF_GEN8N_SH'
#!/usr/bin/env bash
# Gen 8 on this box, a follow-on cohort (gen8n.sh; from gen8.sh): the arena's main mix, configs/round8-candidate.json (Max, 12 November 2026, 15:32 UTC "Go ahead",
# 15:33 "All machines not working on 9 and other future projects can switch from 7 work to 8 arena", 16:11 to the operator:
# "I want to switch the arena to gen 8 ... Can you help make sure the collectors switch over?"). Source
# feature/gen8-prototype-20261112 at 792c4cb; notice docs/gen8_candidate_2026-11-12.md there. The cohort takes over the
# unplayed deals of a drained cohort of this box (OLD in gen8.env) without the families policy v4.1 was trained on
# (Max, 15:50: never in the arena): the union of the two lists, 34,092 families.
#
#   gen8.sh build | tests | prepare | preflight | records | units | start WORKERS | status
set -euo pipefail
W=$HOME/work; PY=$W/venv/bin/python; SRC=$W/sdb-gen8; S=$W/gen8
COMMIT=792c4cb
LIST=$S/v41-training-families-union.json; LISTSHA=0b8ac2b7f41b91915f518c42f76701728097b4151acb5d0e964051c261eca0e2
. "$S/next.env"      # BOX, OLD (a drained cohort whose unplayed deals this one takes over), TAG, SRCDESC (where OLD came from)
RUN=$W/runs/gen8-$TAG-$BOX; PUB=$W/publication/gen8-$TAG-$BOX; BRANCH=arena-gen8-$TAG-$BOX-feed
PLAN=$SRC/configs/round8-candidate.json
U=$(id -un)
CAPS="OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TF_NUM_INTRAOP_THREADS=1 TF_NUM_INTEROP_THREADS=1 TF_CPP_MIN_LOG_LEVEL=3"
SSH="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
REMOTE=git@github.com:maxschireson/Single-Dummy-Bridge.git
say() { echo "$(date -u +%T) $*"; }


cmd_build() {
  if [ ! -d "$SRC/.git" ]; then git init -q "$SRC" && git -C "$SRC" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; fi
  git -C "$SRC" fetch -q --depth 30 origin feature/gen8-prototype-20261112 && git -C "$SRC" checkout -q "$COMMIT" || { say "could not check out $COMMIT"; exit 1; }
  say "checkout: $(git -C "$SRC" log -1 --format='%H %s' | cut -c1-110)"
  cd "$SRC"
  for r in models/*/*/restore*.py; do
    (cd "$(dirname "$r")" && "$PY" "$(basename "$r")" >/dev/null 2>/tmp/restore.err) || say "FAILED $r: $(tail -1 /tmp/restore.err)"
  done
  "$PY" scripts/build_dds.py >/dev/null 2>&1 || true
  [ -s bridge_harness/libbridge_dds.so ] || { say "DDS library was not built"; exit 1; }
  say "v4.1 $(sha256sum models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz | cut -c1-16); system scorer $(sha256sum models/cardplay/gen8-system-scorer-v1-2026-11-12/*.npz 2>/dev/null | head -1 | cut -c1-16); dds library $(sha256sum bridge_harness/libbridge_dds.so | cut -c1-16) (phase 1 checkout: $(sha256sum $W/sdb-gen7-arena/bridge_harness/libbridge_dds.so | cut -c1-16))"
}

cmd_tests() {
  cd "$SRC"; local start; start=$(date +%s)
  local out bad=
  for pattern in "test_gen8*.py" "test_gen71*.py" "test_rule_bidder.py" "test_bidding_systems.py"; do
    out=$(env $CAPS "$PY" -m unittest discover -s tests -p "$pattern" 2>&1 | grep -E "^(Ran|OK|FAILED|ERROR:|FAIL:)" | tr '\n' ' ' | cut -c1-600) || true
    say "tests $pattern: $out"
    case "$out" in *" OK"*) ;; *) bad=1 ;; esac
  done
  say "tests took $(( $(date +%s) - start ))s"
  [ -z "$bad" ] || { say "the Gen 8 tests did not pass"; exit 1; }
}

cmd_prepare() {
  [ "$(git -C "$SRC" rev-parse --short=7 HEAD)" = "$COMMIT" ] || { say "source is not at $COMMIT"; exit 1; }
  [ -e "$RUN" ] && { say "$RUN already exists; not overwriting"; exit 1; }
  [ -e "$PUB" ] && { say "$PUB already exists; not overwriting"; exit 1; }
  if GIT_SSH_COMMAND="$SSH" git ls-remote --exit-code --heads "$REMOTE" "$BRANCH" >/dev/null 2>&1; then say "branch $BRANCH already exists on GitHub"; exit 1; fi
  # The source run is a Gen 7 cohort of this box. It has to be finished: stopped, collectors gone, records published.
  [ -e "$OLD/STOP" ] || { say "$OLD has no STOP file"; exit 1; }
  [ "$(sha256sum "$LIST" | cut -c1-64)" = "$LISTSHA" ] || { say "the list of training families is not the expected file"; exit 1; }
  for unit in arena-gen7 arena-gen71; do
    [ "$(systemctl is-active $unit 2>/dev/null)" = active ] && { say "the collector $unit is still running"; exit 1; }
  done
  # The box's current Gen 8 cohort may run meanwhile; the source must not be it.
  local cur; cur=$(systemctl show -p ExecStart --value arena-gen8 | sed -n 's/.*--run \([^ ;]*\).*/\1/p' | head -1)
  [ "$(readlink -f "$OLD")" != "$(readlink -f "${cur:-/nonexistent}")" ] || { say "$OLD is the cohort arena-gen8 runs"; exit 1; }
  [ -z "$(ls "$OLD/failures" 2>/dev/null)" ] || { say "the source cohort has failure records"; exit 1; }
  local played published
  played=$(ls "$OLD/receipts" | wc -l)
  if [ "$played" -gt 0 ] && [ ! -e "$OLD/FROM_FEED" ]; then         # a never-played claim cohort has no publisher; a copy of a feed's recovery/ is published by definition
    published=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$OLD/publisher-status.json")
    [ "$played" = "$published" ] || { say "the source cohort has published $published of $played boards; publish the rest first"; exit 1; }
  fi
  [ -e "$OLD/WATCHDOG_STOP" ] || echo "Finished for good on $(date -u +%FT%TZ): the arena went to Gen 8 (Max, 15:32 and 16:11 UTC). Its unplayed deals not from the families the policy net v4.1 was trained on went to $(basename "$RUN"). No watchdog ran on this box." > "$OLD/WATCHDOG_STOP"
  cd "$SRC"
  "$PY" ops/prepare_gen7_alpha.py --source "$OLD" --run "$RUN" --plan "$PLAN" --exclude-families "$LIST" > "$S/prepare-gen8.json"
  "$PY" - "$S/prepare-gen8.json" "$OLD" "$RUN" "$played" "$LIST" "$LISTSHA" "$PLAN" <<'PYEOF'
import glob, json, os, sys
sys.path.insert(0, os.getcwd())
from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load
d = json.load(open(sys.argv[1])); old = json.load(open(sys.argv[2] + '/manifest.json')); m = json.load(open(sys.argv[3] + '/manifest.json')); played = int(sys.argv[4])
trained = set(json.load(open(sys.argv[5])))
done = {json.load(open(p))['family'] for p in glob.glob(sys.argv[2] + '/receipts/*.json')}
old_fams = [deal_key(b.hands, True) for b in load(os.path.join(sys.argv[2], old['corpus']))]
new_fams = [deal_key(b.hands, True) for b in load(os.path.join(sys.argv[3], m['corpus']))]
expect = [f for f in old_fams if f not in done and f not in trained]
assert new_fams == expect, 'the new corpus is not the old unplayed deals without the training families, in order'
assert not set(new_fams) & trained and len(set(new_fams)) == len(new_fams)
ex = m['evaluation_exclusions']
assert ex['sha256'] == sys.argv[6] and ex['families'] == len(trained), ex
left_out = sum(1 for f in old_fams if f not in done and f in trained)
plan = json.load(open(sys.argv[7]))
assert d['allocation'] == plan['pair_weights'], d['allocation']
ids = {k: m['bots'][k]['identity'][:12] for k in ('8s-32', '8c-32', '71s-32', '5RZ32', '1')}
assert ids == {'8s-32': '269fdf1854f4', '8c-32': 'f60c9782f5c8', '71s-32': '7b0f58b4c403', '5RZ32': '54591b0880b1', '1': '5ba471c0a612'}, ids
assert m['target'] == old['target'] - played - left_out == len(new_fams) and m['source_generation'] == old['identity'] and m['source_completed'] == played
print(f"cohort {d['identity'][:12]}: {d['target']} deals taken over from cohort {old['identity'][:12]} ({played} of its {old['target']} were played, {left_out} unplayed deals from training families left out); pairs {d['allocation']}; "
      f"bots {ids}; systems {m.get('systems')}; gen8 {json.dumps(m.get('gen8'))[:160]}; audit {m['audit']}; gap forks {m.get('gap_fork')}; exclusions {ex['families']} families, sha256 {ex['sha256'][:16]}")
PYEOF
}

cmd_preflight() {
  cd "$SRC"; local start; start=$(date +%s)
  if ! env $CAPS "$PY" ops/smoke_gen7.py --run "$RUN" --out "$RUN/preflight.json" --deals 2 > "$S/preflight-gen8.log" 2>&1; then
    say "preflight FAILED"; grep -v -E "absl|oneDNN|cpu_feature|AVX|^WARNING" "$S/preflight-gen8.log" | tail -14 | cut -c1-300; exit 1
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
  env TF_CPP_MIN_LOG_LEVEL=3 SRCDESC="$SRCDESC" "$PY" - "$RUN" "$BOX" "$COMMIT" "$BRANCH" "$(basename "$OLD")" 2>/dev/null <<'PYEOF'
import json, os, platform, sys, time
run, box, commit, branch, old = sys.argv[1:6]
import numpy, scipy, tensorflow as tf
cpu = next((l.split(':', 1)[1].strip() for l in open('/proc/cpuinfo') if l.lower().startswith('model name')), None)
json.dump(dict(host=box, machine='Azure Standard_F8as_v6, 8 vCPUs, 32 GB', cpu=cpu, os=platform.platform(), python=sys.version.split()[0],
    packages=dict(tensorflow=tf.__version__, numpy=numpy.__version__, scipy=scipy.__version__),
    source_repository='https://github.com/maxschireson/Single-Dummy-Bridge', source_branch='feature/gen8-prototype-20261112', source_commit=commit, generation='Gen 8 candidate: 8s-32 and 8c-32 (the Precision rule bidder), with Gen 7.1, Gen 5 and Gen 1',
    source_run=f"{os.environ.get('SRCDESC') or 'this machine' + chr(39) + 's drained cohort ' + old}: the deals it had not played, without the families the policy net v4.1 was trained on (the union of the two lists; artifacts/validation/evaluation-exclusions.json)",
    capture='tie audits, tree audits, gap forks and the guess-size fields (this source has the capture port merged)',
    plan='configs/round8-candidate.json as it is (plan.json beside this file)', memory='unit gen8-recycle restarts the collector after the boards in hand when the box has under 5 GB of memory available', threads='one BLAS, OpenMP and TensorFlow thread a worker',
    publication_branch=branch, supervision='systemd units arena-gen8 and arena-gen8-publish; no BEN pair in this cohort',
    operator='Claude session https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ, through the boxctl agent (docs/boxctl.md)'),
    open(os.path.join(run, 'environment.json'), 'w'), indent=1)
json.dump(dict(launched_epoch=time.time(),
    authority="Max, 12 November 2026, 15:32 UTC: Go ahead (Gen 8); 15:33: machines on Gen 7 work switch to the Gen 8 arena; 15:50: never a board in a family the bot was trained on; 16:11, to the operator: switch the arena to Gen 8. (Earlier: 05:42 UTC: push 7.1 from 06:00 UTC unless revoked; replace the 7.0 self play with 7.0/7.1 matches for at least 1000 boards / until 7.1 establishes a 95% CI lead. 05:54 UTC: 'We can switch azure 2 to 100% 7.1 vs 7.0; 7 is clearly a big step vs 6.'",
    notice='docs/gen8_candidate_2026-11-12.md on feature/gen8-prototype-20261112', host=box,
    reason='the arena goes to Gen 8',
    steps='prepare from the drained cohort with --exclude-families, preflight with ops/smoke_gen7.py, then the collector under systemd'),
    open(os.path.join(run, 'launch.json'), 'w'), indent=1)
PYEOF
  mkdir -p "$PUB" && git -C "$PUB" init -q && git -C "$PUB" checkout -q --orphan "$BRANCH"
  git -C "$PUB" remote add origin "$REMOTE"
  git -C "$PUB" config core.sshCommand "$SSH"
  git -C "$PUB" config user.name "Claude"; git -C "$PUB" config user.email "noreply@anthropic.com"
  cat > "$PUB/.git/hooks/commit-msg" <<'HOOK'
#!/bin/sh
grep -q "^Claude-Session:" "$1" || printf '\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ\n' >> "$1"
HOOK
  chmod +x "$PUB/.git/hooks/commit-msg"
  say "records written; publication checkout on $BRANCH"
}

cmd_units() {
  [ -e "$S/workers.env" ] || echo "WORKERS=2" > "$S/workers.env"
  sudo tee /etc/systemd/system/arena-gen8.service >/dev/null <<UNIT
[Unit]
Description=Gen 8 collector: the main mix, deals v4.1 was not trained on
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
  sudo tee /etc/systemd/system/arena-gen8-publish.service >/dev/null <<UNIT
[Unit]
Description=Gen 8 feed publisher
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
  sudo systemctl start arena-gen8
  while [ "$(boards)" -lt "$want" ] && [ $(( $(date +%s) - start )) -lt 2400 ] && [ "$(systemctl is-active arena-gen8)" = active ]; do sleep 10; done
  touch "$RUN/STOP"
  for i in $(seq 1 120); do [ "$(systemctl is-active arena-gen8)" = active ] || break; sleep 10; done
  say "trial: $(boards) boards in $(( $(date +%s) - start ))s with two workers; collector now $(systemctl is-active arena-gen8); failures: $(ls "$RUN/failures" | tr '\n' ' ')"
  [ -z "$(ls "$RUN/failures")" ] || { for f in "$RUN"/failures/*.json; do cut -c1-600 "$f"; echo; done; tail -5 "$S/collector.log" | cut -c1-300; exit 1; }
}

cmd_publish() {     # one publication, then the publisher stays up
  cd "$SRC"
  env $CAPS "$PY" ops/publish_gen5.py --run "$RUN" --publication "$PUB" --once > "$S/publish-once.log" 2>&1 || { say "publication FAILED"; tail -8 "$S/publish-once.log" | cut -c1-300; exit 1; }
  say "published: $(git -C "$PUB" log -1 --format='%h %s' | cut -c1-90) on $BRANCH"
  sudo systemctl enable --now arena-gen8-publish >/dev/null 2>&1 || true
}

cmd_start() {       # the collector at full strength
  # Eight new workers opening a solver cache that does not exist yet can collide on it (seen on this box on 12 November:
  # "database is locked"). Create it first with the statements bridge_harness/dds_cache.py itself runs.
  # The solver cache goes on a RAM disk (eight workers share it; on disk they waited on its fsyncs and write lock about a third of
  # the time on azure2): tmpfs /mnt/ddscache, also in /etc/fstab.
  M=/mnt/ddscache; T=$M/$(basename "$RUN").sqlite
  if ! mountpoint -q $M; then sudo mkdir -p $M && sudo mount -t tmpfs -o size=12G,mode=0700,uid=$(id -u),gid=$(id -g),nosuid,nodev tmpfs $M; fi
  grep -q " $M tmpfs " /etc/fstab || echo "tmpfs $M tmpfs size=12G,mode=0700,uid=$(id -u),gid=$(id -g),nosuid,nodev 0 0" | sudo tee -a /etc/fstab >/dev/null
  [ -e "$RUN/dds-cache.sqlite" ] || [ -L "$RUN/dds-cache.sqlite" ] || ln -s "$T" "$RUN/dds-cache.sqlite"
  [ -e "$T" ] || "$PY" - "$T" <<'PYEOF'
import sqlite3, sys
db = sqlite3.connect(sys.argv[1], timeout=60)
db.execute('PRAGMA journal_mode=WAL')
db.execute('PRAGMA synchronous=FULL')
db.execute('CREATE TABLE IF NOT EXISTS positions (solver BLOB NOT NULL, position BLOB NOT NULL, scores BLOB NOT NULL,PRIMARY KEY(solver,position)) WITHOUT ROWID')
db.commit(); db.close()
PYEOF
  echo "WORKERS=$1" > "$S/workers.env"; rm -f "$RUN/STOP"
  sudo systemctl enable --now arena-gen8 >/dev/null 2>&1 || true
  sudo systemctl enable --now arena-gen8-publish >/dev/null 2>&1 || true
  say "collector $(systemctl is-active arena-gen8) with $1 workers, publisher $(systemctl is-active arena-gen8-publish), feed $BRANCH"
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
print(f"cohort {m['identity'][:12]}: {len(rs)} of {m['target']} boards; last 10 min {sum(r['completed_epoch'] > now - 600 for r in rs)}; collector {unit('arena-gen8')}, "
      f"publisher {unit('arena-gen8-publish')} [{pub}]; STOP {os.path.exists(run + '/STOP')}; failures {sorted(os.listdir(run + '/failures'))}")
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
EOF_GEN8N_SH
cat > "$S/next8.sh" <<'EOF_NEXT8_SH'
#!/usr/bin/env bash
# Unit next8: when the cohort under arena-gen8 has played all its deals and published them, finish it and start the
# prepared follow-on cohort (gen8n.sh, next.env) with eight workers; then exit. ~/work/gen8/SWITCH_OFF switches it off.
set -uo pipefail
W=$HOME/work; S=$W/gen8; PY=$W/venv/bin/python
. "$S/next.env"; B=$W/runs/gen8-$TAG-$BOX
say() { echo "$(date -u +%FT%TZ) $*"; }
say "started: waiting for the current cohort to finish, then $(basename "$B")"
[ -e "$B/manifest.json" ] && [ -e "$B/preflight.json" ] && [ -e "$B/launch.json" ] || { say "$(basename "$B") is not prepared, preflighted and recorded; exiting"; exit 1; }
while true; do
  sleep 60
  [ -e "$S/SWITCH_OFF" ] && continue
  R=$(systemctl show -p ExecStart --value arena-gen8 | sed -n 's/.*--run \([^ ;]*\).*/\1/p' | head -1)
  [ "$R" = "$B" ] && { say "already on $(basename "$B")"; exit 0; }
  [ -d "$R" ] || continue
  [ -e "$S/recycling" ] && continue
  t=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['target'])" "$R/manifest.json"); k=$(ls "$R/receipts" | wc -l)
  [ "$k" -ge "$t" ] || continue
  [ -z "$(ls "$R/failures")" ] || { say "failure record in $(basename "$R"); not switching"; continue; }
  touch "$S/RECYCLE_OFF" "$R/STOP"         # every deal is played: the collector has nothing left and exits
  for i in $(seq 1 60); do [ "$(systemctl is-active arena-gen8)" = active ] || break; sleep 10; done
  [ "$(systemctl is-active arena-gen8)" = active ] && { say "collector still up 10 minutes after its last deal"; rm -f "$S/RECYCLE_OFF"; continue; }
  for i in $(seq 1 90); do p=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$R/publisher-status.json" 2>/dev/null); [ "$p" = "$k" ] && break; sleep 10; done
  [ "$p" = "$k" ] || { say "feed has $p of $k boards; waiting"; rm -f "$S/RECYCLE_OFF"; continue; }
  say "$(basename "$R") done: $k of $t boards, all published; moving to $(basename "$B")"
  touch "$R/PUBLISH_STOP"; for i in $(seq 1 30); do [ "$(systemctl is-active arena-gen8-publish)" = active ] || break; sleep 5; done
  sudo systemctl stop arena-gen8-publish >/dev/null 2>&1
  [ -e "$R/WATCHDOG_STOP" ] || echo "Finished on $(date -u +%FT%TZ): every deal played and published; the box went on with $(basename "$B"). No watchdog ran on this box." > "$R/WATCHDOG_STOP"
  if [ -L "$R/dds-cache.sqlite" ]; then T=$(readlink "$R/dds-cache.sqlite"); case "$T" in /mnt/ddscache/*) rm -f "$T" "$T-wal" "$T-shm";; esac; fi
  bash "$S/gen8n.sh" units && bash "$S/gen8n.sh" start 8
  rm -f "$S/RECYCLE_OFF"
  say "collector $(systemctl is-active arena-gen8), publisher $(systemctl is-active arena-gen8-publish) on $(basename "$B")"
  exit 0
done
EOF_NEXT8_SH
cat > "$S/prepnext.sh" <<'EOF_PREPNEXT_SH'
#!/usr/bin/env bash
# Unit prepnext8: prepare, preflight and record this box's next Gen 8 cohort while the current one plays, then arm next8.
#   MODE=feed: the source is a copy of the recovery/ folder of a drained cohort's published feed (FEED, EXPECT, PLAYED);
#   MODE=local: the source is a drained run folder on this box (OLD).
set -uo pipefail
W=$HOME/work; S=$W/gen8; PY=$W/venv/bin/python; SRC=$W/sdb-gen8
say() { echo "$(date -u +%T) $*"; }
say "load $(cut -d' ' -f1-3 /proc/loadavg); memory available $(free -m | awk 'NR==2{print $7}') MB; tag $TAG, mode $MODE"
[ "$(git -C "$SRC" rev-parse --short=7 HEAD)" = 792c4cb ] || { say "checkout is not at 792c4cb"; exit 1; }
if [ "$MODE" = feed ]; then
  OLD=$W/sources/$FEED
  if [ ! -e "$OLD/manifest.json" ]; then
    T=$(mktemp -d); git clone -q --depth 1 --single-branch --branch "$FEED" https://github.com/maxschireson/Single-Dummy-Bridge "$T/c" || { say "clone of $FEED failed"; exit 1; }
    C=$(git -C "$T/c" rev-parse HEAD); mkdir -p "$W/sources"; cp -a "$T/c/recovery" "$OLD"; rm -rf "$T"; mkdir -p "$OLD/failures"
    echo "A copy of recovery/ on $FEED at $C, made on $(date -u +%FT%TZ) by the operator, as the source of a Gen 8 cohort's deals. Never run here." > "$OLD/FROM_FEED"
    [ -e "$OLD/WATCHDOG_STOP" ] || echo "$WDNOTE (copy of $FEED at $C)" > "$OLD/WATCHDOG_STOP"
  fi
  "$PY" - "$OLD" "$EXPECT" "$PLAYED" <<'PYEOF' || exit 1
import glob, json, sys
run, expect, played = sys.argv[1], sys.argv[2], int(sys.argv[3])
m = json.load(open(run + '/manifest.json')); r = glob.glob(run + '/receipts/*.json'); e = glob.glob(run + '/episodes/*.json.gz')
assert m['identity'].startswith(expect), m['identity'][:12]
assert len(r) == len(e) == played, (len(r), len(e))
print(f"source {m['identity'][:12]}: {m['target']} deals, {len(r)} played, STOP and WATCHDOG_STOP present")
PYEOF
  SRCDESC="cohort $EXPECT ($DESC), copied from recovery/ on $FEED at $(sed -n 's/.* at \([0-9a-f]\{40\}\),.*/\1/p' "$OLD/FROM_FEED")"
else
  SRCDESC="this machine's drained cohort $(basename "$OLD") ($DESC)"
fi
printf 'BOX=%s\nOLD=%s\nTAG=%s\nSRCDESC="%s"\n' "$BOXNAME" "$OLD" "$TAG" "$SRCDESC" > "$S/next.env"
for step in prepare preflight records; do
  say "== $step"
  nice -n 5 bash "$S/gen8n.sh" $step || { say "STOPPED at: $step"; exit 1; }
done
sudo tee /etc/systemd/system/next8.service >/dev/null <<UNIT
[Unit]
Description=Start the prepared follow-on Gen 8 cohort when the current one has played and published every deal

[Service]
User=$(id -un)
Environment=HOME=$HOME
ExecStart=$S/next8.sh
StandardOutput=append:$S/next8.log
StandardError=append:$S/next8.log
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload; sudo systemctl enable --now next8 >/dev/null 2>&1
say "next8 $(systemctl is-active next8)"
say DONE
EOF_PREPNEXT_SH
chmod +x "$S/gen8n.sh" "$S/next8.sh" "$S/prepnext.sh"
systemctl is-active --quiet prepnext8 && { echo "prepnext8 already running"; exit 0; }
systemctl is-active --quiet next8 && { echo "next8 already armed"; exit 0; }
[ "$BOXCTL_BOX" = azure6 ] || { echo "this command is for azure6"; exit 1; }
MODE=feed; TAG=s1; FEED=arena-gen7-1-vs70-fresh-azure2-feed; EXPECT=4b32e6ed0d6b; PLAYED=745
DESC="azure2's Gen 7.1 against 7.0 cohort on deals v4.1 was not trained on, capsule shard 1/8, drained at 08:14 UTC on 12 November at 745 boards"
WDNOTE="Drained on azure2 at 08:14 UTC on 12 November 2026 by the operator: STOP, collector and publisher stopped and disabled, every board published; azure2 went to the plan session. No watchdog ran on that box."
sudo systemctl reset-failed prepnext8 2>/dev/null || true
sudo systemd-run --quiet --unit=prepnext8 --uid="$(id -un)" --setenv=HOME="$HOME" --setenv=BOXNAME="$BOXCTL_BOX" --setenv=MODE="$MODE" --setenv=TAG="$TAG" --setenv=FEED="${FEED:-}" --setenv=EXPECT="${EXPECT:-}" --setenv=PLAYED="${PLAYED:-0}" --setenv=DESC="$DESC" --setenv=WDNOTE="${WDNOTE:-}" --setenv=OLD="${OLD:-}" \
  --property=StandardOutput=append:"$S/prepnext8.log" --property=StandardError=append:"$S/prepnext8.log" -- "$S/prepnext.sh"
sleep 40; echo "prepnext8: $(systemctl is-active prepnext8)"; tail -6 "$S/prepnext8.log" | cut -c1-260
