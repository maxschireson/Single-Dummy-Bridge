# boxctl: timeout=60
# azure1: close the last Gen 8 cohort when played out, then 8X v3 on fresh deals (Max, 13 November 2026, 07:1x UTC). Unit go8x; log ~/work/gen8x/go8x.log.
set -euo pipefail
[ "$BOXCTL_BOX" = azure1 ] || { echo "this command is for azure1"; exit 1; }
S=$HOME/work/gen8x
cat > "$S/g8x.sh" <<'EOF_G8X_SH'
#!/usr/bin/env bash
# 8X v3 in the arena on this box (g8x.sh, from gen8n.sh). Max, 13 November 2026: to x8 at 06:40 UTC "Let's put 8X v3 into the mix
# on the arena and see what happens over time", lanes on g7's arena boxes; to the operator at 07:1x UTC: azure1 goes to 8X v3, fresh
# deals. Source feature/gen8x-arena-20261113 (x8's; the Gen 8 launch line with the 8X engine and dave's --fresh prepare). The
# cohort's deals are fresh (bridge_harness.corpus.generate, seed SEED), clear of the 50,818 families policy v4.1 and rollout net v1
# were trained on, of the source's corpus and of every family played on registered feeds (dave's list of 04:26 UTC); the source
# (a drained Gen 8 cohort of this box) supplies bots and artifacts only. 8X asks sure_cpp (SURE_BIN) at most decisions.
#   g8x.sh prepare | preflight | records | units | start WORKERS | status
set -euo pipefail
W=$HOME/work; PY=$W/venv/bin/python; SRC=$W/sdb-gen8x; S=$W/gen8x
LIST=$S/gen8x-v3-exclusions.json; LISTSHA=72fafc4cce9ed62e
PLAYED=$S/played-families-20261113.json.gz; PLAYEDSHA=ac5243e11112bf68fbc6a8c8700cf6b36ab829a2348f5925c5fcf721c567333c
SURE_BIN=$S/sure_cpp
. "$S/g8x.env"       # BOX, OLD (a drained Gen 8 cohort: bots and artifacts), COMMIT (pinned checkout), PLANNAME, TAG, FRESH, SEED
RUN=$W/runs/gen8-$TAG-$BOX; PUB=$W/publication/gen8-$TAG-$BOX; BRANCH=arena-gen8-$TAG-$BOX-feed
PLAN=$SRC/configs/$PLANNAME.json
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
  git -C "$SRC" fetch -q --depth 50 origin feature/gen8x-arena-20261113 && git -C "$SRC" checkout -q "$COMMIT" || { say "could not check out $COMMIT"; exit 1; }
  [ "$(git -C "$SRC" rev-parse HEAD)" = "$COMMIT" ] || { say "source is not at $COMMIT"; exit 1; }
  [ -x "$SURE_BIN" ] || { say "no sure_cpp at $SURE_BIN"; exit 1; }
  [ "$(sha256sum "$PLAYED" | cut -c1-64)" = "$PLAYEDSHA" ] || { say "the played list is not dave's file"; exit 1; }
  [ -e "$RUN" ] && { say "$RUN already exists; not overwriting"; exit 1; }
  [ -e "$PUB" ] && { say "$PUB already exists; not overwriting"; exit 1; }
  if GIT_SSH_COMMAND="$SSH" git ls-remote --exit-code --heads "$REMOTE" "$BRANCH" >/dev/null 2>&1; then say "branch $BRANCH already exists on GitHub"; exit 1; fi
  # The source run is a Gen 7 cohort of this box. It has to be finished: stopped, collectors gone, records published.
  [ -e "$OLD/STOP" ] || { say "$OLD has no STOP file"; exit 1; }
  [ "$(sha256sum "$LIST" | cut -c1-16)" = "$LISTSHA" ] || { say "the list of training families is not the expected file"; exit 1; }
  for unit in arena-gen7 arena-gen71; do
    [ "$(systemctl is-active $unit 2>/dev/null)" = active ] && { say "the collector $unit is still running"; exit 1; }
  done
  [ -e "$OLD/WATCHDOG_STOP" ] || { say "$OLD is not closed (no WATCHDOG_STOP)"; exit 1; }
  [ -z "$(ls "$OLD/failures" 2>/dev/null)" ] || { say "the source cohort has failure records"; exit 1; }
  local played published
  played=$(ls "$OLD/receipts" | wc -l)
  if [ "$played" -gt 0 ] && [ ! -e "$OLD/FROM_FEED" ]; then
    published=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$OLD/publisher-status.json")
    [ "$played" = "$published" ] || { say "the source cohort has published $published of $played boards; publish the rest first"; exit 1; }
  fi
  cd "$SRC"
  env SURE_BIN="$SURE_BIN" "$PY" ops/prepare_gen7_alpha.py --source "$OLD" --run "$RUN" --plan "$PLAN" --exclude-families "$LIST" --fresh "$FRESH" --fresh-seed "$SEED" --played "$PLAYED" > "$S/prepare-gen8x.json"
  "$PY" - "$S/prepare-gen8x.json" "$OLD" "$RUN" "$played" "$LIST" "$LISTSHA" "$PLAN" "$FRESH" "$SEED" "$PLAYED" <<'PYEOF'
import glob, json, os, sys
sys.path.insert(0, os.getcwd())
from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load
d = json.load(open(sys.argv[1])); old = json.load(open(sys.argv[2] + '/manifest.json')); m = json.load(open(sys.argv[3] + '/manifest.json')); played = int(sys.argv[4])
trained = set(json.load(open(sys.argv[5])))
import gzip
fresh, seed = int(sys.argv[8]), int(sys.argv[9]); played_list = set(json.load(gzip.open(sys.argv[10], 'rt')))
old_fams = set(deal_key(b.hands, True) for b in load(os.path.join(sys.argv[2], old['corpus'])))
new_fams = [deal_key(b.hands, True) for b in load(os.path.join(sys.argv[3], m['corpus']))]
assert len(new_fams) == len(set(new_fams)) == fresh == m['target'], (len(new_fams), m['target'])
assert not set(new_fams) & trained and not set(new_fams) & old_fams and not set(new_fams) & played_list, 'a fresh deal is a training, source or played family'
fd = m['fresh_deals']; assert fd['seed'] == seed and fd['count'] == fresh, fd
ex = m['evaluation_exclusions']
assert ex['sha256'].startswith(sys.argv[6]) and ex['families'] == len(trained) == 50818, ex
plan = json.load(open(sys.argv[7]))
assert d['allocation'] == plan['pair_weights'], d['allocation']
ids = {k: v['identity'][:12] for k, v in m['bots'].items() if k in ('8s-32', '71s-32', '5RZ32', '1') or k.startswith('8x')}
assert ids['8s-32'] == '269fdf1854f4' and ids['71s-32'] == '7b0f58b4c403' and ids['5RZ32'] == '54591b0880b1' and ids['1'] == '5ba471c0a612', ids
print(f"cohort {d['identity'][:12]}: {d['target']} fresh deals (seed {seed}; excluded {fd['excluded']}), bots and artifacts from {old['identity'][:12]}; pairs {d['allocation']}; "
      f"bots {ids}; audit {m['audit']}; exclusions {ex['families']} families, sha256 {ex['sha256'][:16]}")
PYEOF
}

cmd_preflight() {
  cd "$SRC"; local start; start=$(date +%s)
  if ! env $CAPS SURE_BIN="$SURE_BIN" "$PY" ops/smoke_gen7.py --run "$RUN" --out "$RUN/preflight.json" --deals 2 > "$S/preflight-gen8x.log" 2>&1; then
    say "preflight FAILED"; grep -v -E "absl|oneDNN|cpu_feature|AVX|^WARNING" "$S/preflight-gen8x.log" | tail -14 | cut -c1-300; exit 1
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
  env TF_CPP_MIN_LOG_LEVEL=3 SRCDESC="$SRCDESC" PLANNAME="$PLANNAME" SURE_BIN="$SURE_BIN" "$PY" - "$RUN" "$BOX" "$COMMIT" "$BRANCH" "$(basename "$OLD")" 2>/dev/null <<'PYEOF'
import json, os, platform, sys, time
run, box, commit, branch, old = sys.argv[1:6]
import numpy, scipy, tensorflow as tf
cpu = next((l.split(':', 1)[1].strip() for l in open('/proc/cpuinfo') if l.lower().startswith('model name')), None)
json.dump(dict(host=box, machine='Azure Standard_F8as_v6, 8 vCPUs, 32 GB', cpu=cpu, os=platform.platform(), python=sys.version.split()[0],
    packages=dict(tensorflow=tf.__version__, numpy=numpy.__version__, scipy=scipy.__version__),
    source_repository='https://github.com/maxschireson/Single-Dummy-Bridge', source_branch='feature/gen8x-arena-20261113', source_commit=commit, generation='8X v3 (x8): 8s-32 card for card through trick 6, then rollout-net re-valuation in games, slams and doubled contracts; against Gen 8, Gen 7.1, Gen 5 and Gen 1',
    source_run=f"{os.environ.get('SRCDESC')}: bots and artifacts only; the deals are fresh (manifest fresh_deals), clear of the families policy v4.1 and rollout net v1 were trained on (artifacts/validation/evaluation-exclusions.json, 50,818) and of the families played on registered feeds at 04:26 UTC",
    plan=f"configs/{os.environ.get('PLANNAME')}.json as it is (plan.json beside this file)", sure_bin=os.environ.get('SURE_BIN'), sure_source=open(os.path.join(os.path.dirname(os.environ.get('SURE_BIN')), 'sure_cpp.commit')).read().strip(),
    memory='unit gen8x-recycle restarts the collector after the boards in hand when the box has under 5 GB of memory available', threads='one BLAS, OpenMP and TensorFlow thread a process',
    publication_branch=branch, supervision='systemd units arena-gen8x and arena-gen8x-publish; no BEN pair in this cohort; the box also hosts the play-against-Sid server (sidplay)',
    operator='Claude session https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ, through the boxctl agent (docs/boxctl.md)'),
    open(os.path.join(run, 'environment.json'), 'w'), indent=1)
json.dump(dict(launched_epoch=time.time(),
    authority="Max, 13 November 2026: to x8 at 06:40 UTC, put 8X v3 into the mix on the arena, on lanes of g7's arena boxes; to the operator at 07:1x UTC: azure1 goes to 8X v3, fresh deals",
    notice='docs/x8_bot.md on feature/gen8x-arena-20261113', host=box,
    reason='8X v3 into the arena',
    steps='prepare with --fresh, --exclude-families and --played, preflight with ops/smoke_gen7.py (8x3-32 against 8s-32 and 71s-32), then the collector under systemd'),
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
  sudo tee /etc/systemd/system/arena-gen8x.service >/dev/null <<UNIT
[Unit]
Description=8X v3 collector: fresh deals, clear of the v4.1 and rollout net v1 training families
StartLimitIntervalSec=900
StartLimitBurst=3

[Service]
User=$U
WorkingDirectory=$SRC
EnvironmentFile=$S/workers.env
Environment=HOME=$HOME PYTHONUNBUFFERED=1 $CAPS SURE_BIN=$SURE_BIN
ExecStart=$PY -u ops/gen5_runtime.py --run $RUN --workers \${WORKERS}
StandardOutput=append:$S/collector.log
StandardError=append:$S/collector.log
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
UNIT
  sudo tee /etc/systemd/system/arena-gen8x-publish.service >/dev/null <<UNIT
[Unit]
Description=8X v3 feed publisher
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
  sudo systemctl start arena-gen8x
  while [ "$(boards)" -lt "$want" ] && [ $(( $(date +%s) - start )) -lt 2400 ] && [ "$(systemctl is-active arena-gen8x)" = active ]; do sleep 10; done
  touch "$RUN/STOP"
  for i in $(seq 1 120); do [ "$(systemctl is-active arena-gen8x)" = active ] || break; sleep 10; done
  say "trial: $(boards) boards in $(( $(date +%s) - start ))s with two workers; collector now $(systemctl is-active arena-gen8x); failures: $(ls "$RUN/failures" | tr '\n' ' ')"
  [ -z "$(ls "$RUN/failures")" ] || { for f in "$RUN"/failures/*.json; do cut -c1-600 "$f"; echo; done; tail -5 "$S/collector.log" | cut -c1-300; exit 1; }
}

cmd_publish() {     # one publication, then the publisher stays up
  cd "$SRC"
  env $CAPS "$PY" ops/publish_gen5.py --run "$RUN" --publication "$PUB" --once > "$S/publish-once.log" 2>&1 || { say "publication FAILED"; tail -8 "$S/publish-once.log" | cut -c1-300; exit 1; }
  say "published: $(git -C "$PUB" log -1 --format='%h %s' | cut -c1-90) on $BRANCH"
  sudo systemctl enable --now arena-gen8x-publish >/dev/null 2>&1 || true
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
  sudo systemctl enable --now arena-gen8x >/dev/null 2>&1 || true
  sudo systemctl enable --now arena-gen8x-publish >/dev/null 2>&1 || true
  say "collector $(systemctl is-active arena-gen8x) with $1 workers, publisher $(systemctl is-active arena-gen8x-publish), feed $BRANCH"
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
print(f"cohort {m['identity'][:12]}: {len(rs)} of {m['target']} boards; last 10 min {sum(r['completed_epoch'] > now - 600 for r in rs)}; collector {unit('arena-gen8x')}, "
      f"publisher {unit('arena-gen8x-publish')} [{pub}]; STOP {os.path.exists(run + '/STOP')}; failures {sorted(os.listdir(run + '/failures'))}")
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
EOF_G8X_SH
cat > "$S/go8x.sh" <<'EOF_GO8X_SH'
#!/usr/bin/env bash
# Unit go8x (azure1): close the last Gen 8 cohort (gen8-m1-azure1) once it is played out and published, then prepare, preflight,
# record and start 8X v3 on fresh deals with eight workers (Max, 13 November 2026, 07:1x UTC). PLANNAME and TAG from the unit env.
set -uo pipefail
W=$HOME/work; S8=$W/gen8; S=$W/gen8x; PY=$W/venv/bin/python; T=$S/g8x.sh
say() { echo "$(date -u +%T) $*"; }
M1=$W/runs/gen8-m1-azure1
say "load $(cut -d' ' -f1-3 /proc/loadavg); memory available $(free -m | awk 'NR==2{print $7}') MB; plan $PLANNAME, tag $TAG"
# 1. the last Gen 8 cohort: wait until played out and published, then close it
for i in $(seq 1 120); do
  t=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['target'])" "$M1/manifest.json"); k=$(ls "$M1/receipts" | wc -l)
  [ "$k" -ge "$t" ] && [ "$(systemctl is-active arena-gen8)" != active ] && break
  sleep 30
done
[ "$k" -ge "$t" ] || { say "gen8-m1-azure1 not played out ($k of $t)"; exit 1; }
[ -z "$(ls "$M1/failures")" ] || { say "failure record in gen8-m1-azure1"; exit 1; }
for i in $(seq 1 60); do p=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$M1/publisher-status.json" 2>/dev/null); [ "$p" = "$k" ] && break; sleep 10; done
[ "$p" = "$k" ] || { say "gen8-m1-azure1's feed has $p of $k boards"; exit 1; }
touch "$S8/RECYCLE_OFF" "$M1/STOP" "$M1/PUBLISH_STOP"
for i in $(seq 1 30); do [ "$(systemctl is-active arena-gen8-publish)" = active ] || break; sleep 5; done
sudo systemctl disable --now arena-gen8-publish arena-gen8 gen8-recycle next8 >/dev/null 2>&1
[ -e "$M1/WATCHDOG_STOP" ] || echo "Finished on $(date -u +%FT%TZ): every deal played and published ($k of $t), the last of azure1's Gen 8 pools; the box went to 8X v3 (Max, 13 November 2026, 07:1x UTC). No watchdog ran on this box." > "$M1/WATCHDOG_STOP"
if [ -L "$M1/dds-cache.sqlite" ]; then C=$(readlink "$M1/dds-cache.sqlite"); case "$C" in /mnt/ddscache/*) rm -f "$C" "$C-wal" "$C-shm";; esac; fi
say "gen8-m1-azure1 closed: $k of $t boards, all published; arena-gen8, its publisher, gen8-recycle and next8 disabled"
# 2. 8X v3 on fresh deals
cat > "$S/g8x.env" <<ENV
BOX=azure1
OLD=$M1
COMMIT=$COMMIT
PLANNAME=$PLANNAME
TAG=$TAG
FRESH=$FRESH
SEED=$SEED
SRCDESC="azure1's drained Gen 8 cohort gen8-m1-azure1"
ENV
for step in prepare preflight records units; do
  say "== $step"; bash "$T" $step || { say "STOPPED at: $step"; exit 1; }
done
sudo tee /etc/systemd/system/gen8x-recycle.service >/dev/null <<UNIT
[Unit]
Description=Restart the 8X collector after its boards in hand when the box runs short of memory

[Service]
User=$(id -un)
Environment=HOME=$HOME
ExecStart=$S/recycle8x.sh
StandardOutput=append:$S/recycle.log
StandardError=append:$S/recycle.log
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload; sudo systemctl enable --now gen8x-recycle >/dev/null 2>&1
bash "$T" start 8
sleep 300; bash "$T" status
say DONE
EOF_GO8X_SH
cat > "$S/recycle8x.sh" <<'EOF_RECYCLE8X_SH'
#!/usr/bin/env bash
set -uo pipefail
W=$HOME/work; S=$W/gen8x
LIMIT=${LIMIT:-5000}
say() { echo "$(date -u +%FT%TZ) $*"; }
run_dir() { systemctl show -p ExecStart --value arena-gen8x | sed -n 's/.*--run \([^ ;]*\).*/\1/p' | head -1; }
avail() { awk '/^MemAvailable:/ {print int($2/1024)}' /proc/meminfo; }
tree_mb() { local pid; pid=$(systemctl show -p MainPID --value arena-gen8x); [ "${pid:-0}" != 0 ] || { echo 0; return; }; ps -o rss= --pid "$pid" --ppid "$pid" 2>/dev/null | awk '{s+=$1} END {printf "%d", s/1024}'; }
say "started: the collector is restarted after the boards in hand when the box has under $LIMIT MB of memory available"
while true; do
  sleep 30
  [ -e "$S/RECYCLE_OFF" ] && continue
  [ "$(systemctl is-active arena-gen8x)" = active ] || continue
  R=$(run_dir); [ -n "$R" ] && [ -d "$R" ] || continue
  [ -e "$R/STOP" ] && continue
  a=$(avail); [ "$a" -lt "$LIMIT" ] || continue
  t=$(tree_mb)
  if [ "$t" -lt 8000 ]; then say "only $a MB available but the collector holds $t MB; not restarting it"; sleep 600; continue; fi
  say "$a MB available, collector and workers at $t MB; restarting it after the boards in hand ($(basename "$R"))"
  touch "$S/recycling"; touch "$R/STOP"
  for i in $(seq 1 360); do [ "$(systemctl is-active arena-gen8x)" = active ] || break; sleep 5; done
  if [ "$(systemctl is-active arena-gen8x)" = active ]; then say "did not stop in 30 minutes; STOP left in place"; rm -f "$S/recycling"; continue; fi
  if [ -n "$(ls "$R/failures" 2>/dev/null)" ]; then say "failure record $(ls "$R/failures" | tr '\n' ' '); left stopped for inspection"; rm -f "$S/recycling"; continue; fi
  if [ -e "$S/RECYCLE_OFF" ]; then say "switched off meanwhile; left stopped"; rm -f "$S/recycling"; continue; fi
  # A cache on the RAM disk is emptied at each restart: entries are exact solver results for positions of boards already
  # finished, and a new deal almost never reaches the same position, so this bounds the memory it takes.
  if [ -L "$R/dds-cache.sqlite" ]; then T=$(readlink "$R/dds-cache.sqlite"); case "$T" in /mnt/ddscache/*) say "emptying the RAM-disk cache ($(du -m "$T" | cut -f1) MB)"; rm -f "$T" "$T-wal" "$T-shm"
    "$HOME/work/venv/bin/python" -c "import sqlite3,sys; db=sqlite3.connect(sys.argv[1],timeout=60); db.execute('PRAGMA journal_mode=WAL'); db.execute('PRAGMA synchronous=FULL'); db.execute('CREATE TABLE IF NOT EXISTS positions (solver BLOB NOT NULL, position BLOB NOT NULL, scores BLOB NOT NULL,PRIMARY KEY(solver,position)) WITHOUT ROWID'); db.commit(); db.close()" "$T";; esac; fi
  rm -f "$R/STOP"; sudo systemctl reset-failed arena-gen8x 2>/dev/null; sudo systemctl start arena-gen8x
  rm -f "$S/recycling"
  say "restarted with $(ls "$R/receipts" | wc -l) boards done"
done
EOF_RECYCLE8X_SH
chmod +x "$S/g8x.sh" "$S/go8x.sh" "$S/recycle8x.sh"
systemctl is-active --quiet go8x && { echo "go8x already running"; exit 0; }
sudo systemctl reset-failed go8x 2>/dev/null || true
sudo systemd-run --quiet --unit=go8x --uid="$(id -un)" --setenv=HOME="$HOME" --setenv=PLANNAME=round8x-v3 --setenv=TAG=x3 --setenv=COMMIT=3d93d7804bd625e7174f7818719f9917a297ae4c --setenv=FRESH=6000 --setenv=SEED=8380 --property=StandardOutput=append:"$S/go8x.log" --property=StandardError=append:"$S/go8x.log" -- "$S/go8x.sh"
sleep 40; echo "go8x: $(systemctl is-active go8x)"; tail -8 "$S/go8x.log" | cut -c1-260
