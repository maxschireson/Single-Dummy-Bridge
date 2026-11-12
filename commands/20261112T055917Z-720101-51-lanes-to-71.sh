# boxctl: timeout=180
# Gen 7.1 on this box (Max, 12 Nov 05:42 UTC, effective 06:00 UTC): the eight BEN lanes move from 7s-32 to 71s-32 (policy net v4.1).
# The 7.0 lanes are drained and finished, each new lane takes over its unplayed deals, the BEN servers keep running.
# Background unit switch71; progress in ~/work/lanes/switch71.log.
set -euo pipefail
W=$HOME/work; L=$W/lanes; S=$W/gen71; mkdir -p "$S"
[ -e "$S/gen71.env" ] || printf 'BOX=%s\nOLD=%s\n' "$BOXCTL_BOX" "$W/runs/none" > "$S/gen71.env"
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
cat > "$L/lane71.sh" <<'EOF_LANE71_SH'
#!/usr/bin/env bash
# BEN lanes for Gen 7.1 on this box (Max, 12 November 2026, 05:42 UTC: in every match but the 7.0/7.1 comparison,
# 7 becomes 7.1). Each lane's new cohort takes over the deals its Gen 7.0 lane cohort had not played, against the same
# BEN server, which keeps running.
#
# The collector runtime plays BEN boards in one lane (one worker, one BEN server), so one cohort uses about one
# core. To use the whole machine each lane is a cohort of its own: its own shard of the source run, run folder,
# feed branch, BEN server and collector. A lane's server and collector share a private network namespace, so
# every lane reaches its own server at the URL pinned in the bot spec (127.0.0.1 and the BEN bot's port).
#
#   lane71.sh units | plan | prepare LANE | up LANE | preflight LANE | records LANE | start LANE | status
set -euo pipefail
W=$HOME/work; PY=$W/venv/bin/python; SRC=$W/sdb-gen71; BEN=$W/ben; BV=$W/ben-venv; L=$W/lanes
GO=9f5ec19498e7e20e9f610ed93d896880a17cbcc9
BENCOMMIT=9b5f43104aeac713a80b73513f2f2d6daf9f8769
U=$(id -un)
CAPS="OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TF_NUM_INTRAOP_THREADS=1 TF_NUM_INTEROP_THREADS=1 TF_CPP_MIN_LOG_LEVEL=3"
SSH="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
REMOTE=git@github.com:maxschireson/Single-Dummy-Bridge.git
. "$L/role.env"      # BOX, BENID, LABEL, BEN_PORT, CONFNAME, BENNAME
say() { echo "$(date -u +%T) $*"; }
names() { RUN=$W/runs/gen71-$BOX-$LABEL-$1; PUB=$W/publication/gen71-$BOX-$LABEL-$1; BRANCH=arena-gen7-1-$BOX-$LABEL-$1-feed; OLDRUN=$W/runs/gen7-phase1-$BOX-$LABEL-$1; }

cmd_units() {
  cat > "$L/wait-port.sh" <<'SH'
#!/usr/bin/env bash
for i in $(seq 1 200); do (exec 3<>/dev/tcp/127.0.0.1/"$1") 2>/dev/null && exit 0; sleep 5; done
echo "nothing is listening on 127.0.0.1:$1"; exit 1
SH
  chmod +x "$L/wait-port.sh"
  sudo tee /etc/systemd/system/benlane-netns@.service >/dev/null <<UNIT
[Unit]
Description=Private network namespace for BEN lane %i

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c 'ip netns list | grep -qw benlane-%i || ip netns add benlane-%i; ip -n benlane-%i link set lo up'
ExecStop=/bin/sh -c 'ip netns delete benlane-%i || true'

[Install]
WantedBy=multi-user.target
UNIT
  sudo tee /etc/systemd/system/ben-server@.service >/dev/null <<UNIT
[Unit]
Description=BEN server ($BENNAME), lane %i
Requires=benlane-netns@%i.service
After=benlane-netns@%i.service

[Service]
User=$U
NetworkNamespacePath=/run/netns/benlane-%i
WorkingDirectory=$BEN
EnvironmentFile=$L/%i.env
Environment=HOME=$HOME PYTHONUNBUFFERED=1 $CAPS
ExecStart=$BV/bin/python src/gameapi.py --config \${BEN_CONF} --host 127.0.0.1 --port \${BEN_PORT} --record false
StandardOutput=append:$L/%i.ben.log
StandardError=append:$L/%i.ben.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT
  sudo tee /etc/systemd/system/arena-ben@.service >/dev/null <<UNIT
[Unit]
Description=Gen 7.1 collector against $BENNAME, lane %i
Requires=benlane-netns@%i.service
Wants=ben-server@%i.service
After=benlane-netns@%i.service ben-server@%i.service
StartLimitIntervalSec=900
StartLimitBurst=3

[Service]
User=$U
NetworkNamespacePath=/run/netns/benlane-%i
WorkingDirectory=$SRC
EnvironmentFile=$L/%i.env
Environment=HOME=$HOME PYTHONUNBUFFERED=1 $CAPS
TimeoutStartSec=1200
ExecStartPre=$L/wait-port.sh \${BEN_PORT}
ExecStart=$PY -u ops/gen5_runtime.py --run \${RUN} --workers 1
StandardOutput=append:$L/%i.collector.log
StandardError=append:$L/%i.collector.log
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
UNIT
  sudo tee /etc/systemd/system/arena-ben-publish@.service >/dev/null <<UNIT
[Unit]
Description=Gen 7.1 feed publisher, BEN lane %i
After=network-online.target
Wants=network-online.target

[Service]
User=$U
WorkingDirectory=$SRC
EnvironmentFile=$L/%i.env
Environment=HOME=$HOME PYTHONUNBUFFERED=1 $CAPS
ExecStart=$PY -u ops/publish_gen5.py --run \${RUN} --publication \${PUB}
StandardOutput=append:$L/%i.publisher.log
StandardError=append:$L/%i.publisher.log
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
UNIT
  sudo systemctl daemon-reload
  cat > "$L/smoke_ben16_71.py" <<'PYEOF'
#!/usr/bin/env python3
"""Preflight for a cohort whose only Gen 7 pair is against BEN (16).

ops/smoke_gen7.py leaves out any pair with the bot id 'ben' (BEN (16)), so on such a cohort it finds no pair to
play. This runs that file's own smoke() with that one condition removed and nothing else changed: the same
gen5_runtime.play path and the same check_decision. It lives outside the pinned source tree.
"""
import argparse
import inspect
import json
import sys
from pathlib import Path

SRC = Path.home() / 'work' / 'sdb-gen71'
sys.path.insert(0, str(SRC))
import ops.smoke_gen7 as stock

source = inspect.getsource(stock.smoke)
skip = " and 'ben' not in pair_members(p)"
assert source.count(skip) == 1, 'ops/smoke_gen7.py changed; check this wrapper'
exec(compile(source.replace(skip, ''), str(SRC / 'ops' / 'smoke_gen7.py'), 'exec'), stock.__dict__)
p = argparse.ArgumentParser()
p.add_argument('--run', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--deals', type=int, default=2)
p.add_argument('--start', type=int, default=0)
a = p.parse_args()
r = stock.__dict__['smoke'](a.run, a.out, a.deals, a.start)
report = json.loads(a.out.read_text())
report['preflight_note'] = "ops/smoke_gen7.py smoke() with its exclusion of the pair id 'ben' removed, so that the BEN (16) pair is played"
a.out.write_text(json.dumps(report))
print(json.dumps(dict(tree=r['tree'], phases=r['phases']), indent=1))
PYEOF
  say "units and preflight wrapper written"
}

cmd_plan() {
  [ "$(git -C "$SRC" rev-parse HEAD)" = "$GO" ] || { say "source is not at $GO"; exit 1; }
  "$PY" - "$SRC/configs/round71-ben.json" "$L/plan71-$LABEL.json" "$BENID" "$BENNAME" "$BOX" <<'PYEOF'
import json, sys
src, dst, benid, benname, box = sys.argv[1:6]
p = json.load(open(src))
assert p['launch_enabled'] is True and not p['pending'], 'the Gen 7.1 BEN plan is not open'
pair = '71s-32~' + benid
assert pair in p['pair_weights'], pair
p['roster'] = ['71s-32', benid]
p['pair_weights'] = {pair: 1}
p['title'] = f'Gen 7.1 · {benname} pair on {box}: standard with policy v4.1 against {benname}'
p['notes'] = list(p.get('notes', [])) + [
    f"This copy of configs/round71-ben.json keeps one of its two pairs, {pair}: one Azure machine plays each BEN level (Max, 12 November 2026, 03:26 UTC). "
    f"Only the roster, the pair weights, the title and this note differ from that file."]
json.dump(p, open(dst, 'w'), indent=1)
tree = p['gen7_bots']['71s-32']['gen7']['tree'][0]
print('plan:', p['title'], '| pairs', p['pair_weights'], '| policy', p['gen7_bots']['71s-32']['policy'], '| tree', {k: tree[k] for k in ('root_margin', 'trust', 'path', 'tricks')})
PYEOF
}

cmd_prepare() {
  local lane=$1; names "$lane"
  [ -e "$RUN" ] && { say "$RUN already exists; not overwriting"; exit 1; }
  [ -e "$PUB" ] && { say "$PUB already exists; not overwriting"; exit 1; }
  if GIT_SSH_COMMAND="$SSH" git ls-remote --exit-code --heads "$REMOTE" "$BRANCH" >/dev/null 2>&1; then say "branch $BRANCH already exists on GitHub"; exit 1; fi
  # The source run is this lane's Gen 7.0 cohort. It has to be finished: stopped, collector gone, every board published.
  [ -e "$OLDRUN/STOP" ] || { say "lane $lane: the 7.0 cohort has no STOP file"; exit 1; }
  [ "$(systemctl is-active "arena-ben@$lane")" = active ] && { say "lane $lane: its collector is still running"; exit 1; }
  [ -z "$(ls "$OLDRUN/failures" 2>/dev/null)" ] || { say "lane $lane: the 7.0 cohort has failure records"; exit 1; }
  local played published
  played=$(ls "$OLDRUN/receipts" | wc -l)
  published=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$OLDRUN/publisher-status.json")
  [ "$played" = "$published" ] || { say "lane $lane: the 7.0 feed has $published of $played boards"; exit 1; }
  [ -e "$OLDRUN/WATCHDOG_STOP" ] || echo "Finished for good on $(date -u +%FT%TZ): Max, 12 November 2026, 05:42 UTC, replaced Gen 7 by Gen 7.1 in this match. The deals this cohort had not played go to $(basename "$RUN"). No watchdog ran on this box." > "$OLDRUN/WATCHDOG_STOP"
  cd "$SRC"
  "$PY" ops/prepare_gen7_alpha.py --source "$OLDRUN" --run "$RUN" --plan "$L/plan71-$LABEL.json" > "$L/$lane.prepare71.json"
  "$PY" - "$L/$lane.prepare71.json" "$BENID" "$lane" "$OLDRUN" "$RUN" "$played" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1])); benid, lane = sys.argv[2:4]; old = json.load(open(sys.argv[4] + '/manifest.json')); m = json.load(open(sys.argv[5] + '/manifest.json')); played = int(sys.argv[6])
tree = d['gen7']['71s-32']['tree'][0]
assert d['allocation'] == {'71s-32~' + benid: 1}, d['allocation']
assert (tree['root_margin'], tree['trust'], tree['path'], tree['tricks']) == (0.25, 0.3, 0.5, 3), 'not the authorized tree settings'
a, b = old['bots']['7s-32'], m['bots']['71s-32']
assert m['bots']['7s-32'] == a and {k for k in a if a[k] != b.get(k)} == {'id', 'identity', 'gen7_policy', 'artifact_sha256'}, '71s-32 differs from 7s-32 in more than the net'
assert b['artifact_sha256']['gen7_policy'] == 'cb3fcfd5c55873735ee22ea5e7ba04606794bed38d261fdf3f1b3a4af5c9fbed'
assert m['target'] == old['target'] - played and m['source_generation'] == old['identity']
print(f"lane {lane}: cohort {d['identity'][:12]}, {d['target']} deals taken over from the 7.0 lane cohort {old['identity'][:12]} ({played} played), pairs {d['allocation']}, 71s-32 {b['identity'][:12]}")
PYEOF
  cat > "$L/$lane.env" <<ENV
RUN=$RUN
PUB=$PUB
BEN_PORT=$BEN_PORT
BEN_CONF=$RUN/assets/$CONFNAME
XDG_CACHE_HOME=$L/$lane.cache
ENV
}

cmd_up() {
  local lane=$1; names "$lane"
  sudo systemctl enable --now "benlane-netns@$lane.service" "ben-server@$lane.service" >/dev/null 2>&1 || true
  if [ ! -e /run/netns/benlane-"$lane" ]; then say "lane $lane: no network namespace"; systemctl status "benlane-netns@$lane" --no-pager 2>&1 | tail -6; return 1; fi
  for i in $(seq 1 120); do
    if sudo nsenter --net=/run/netns/benlane-"$lane" -- bash -c "(exec 3<>/dev/tcp/127.0.0.1/$BEN_PORT) 2>/dev/null"; then say "lane $lane: BEN server listening"; return 0; fi
    sleep 5
  done
  say "lane $lane: BEN server did not come up"; tail -15 "$L/$lane.ben.log" | cut -c1-200; return 1
}

cmd_preflight() {
  local lane=$1; names "$lane"; local start; start=$(date +%s)
  local smoke="ops/smoke_gen7.py"; [ "$BENID" = ben ] && smoke="$L/smoke_ben16_71.py"
  cd "$SRC"
  if ! sudo nsenter --net=/run/netns/benlane-"$lane" -- sudo -u "$U" -H env $CAPS "$PY" "$smoke" --run "$RUN" --out "$RUN/preflight.json" > "$L/$lane.preflight.log" 2>&1; then
    say "lane $lane: preflight FAILED"; grep -v -E "absl|oneDNN|cpu_feature|AVX|^WARNING" "$L/$lane.preflight.log" | tail -12 | cut -c1-300; return 1
  fi
  "$PY" - "$RUN/preflight.json" "$lane" "$(( $(date +%s) - start ))" <<'PYEOF'
import json, sys
r = json.load(open(sys.argv[1])); t = r['tree']
print(f"lane {sys.argv[2]}: preflight passed in {sys.argv[3]}s:", [(d['pair'], d['index'], d['decisions'], round(d['seconds'])) for d in r['deals']],
      '| tree consulted', t['consulted'], 'moved', t['moved'], 'over budget', t['over_budget'])
PYEOF
}

cmd_records() {
  local lane=$1; names "$lane"
  cp "$L/plan71-$LABEL.json" "$RUN/plan.json"
  "$PY" -m pip freeze 2>/dev/null > "$RUN/runtime-requirements.txt"
  env TF_CPP_MIN_LOG_LEVEL=3 "$PY" - "$RUN" "$BOX" "$lane" "$(cat "$L/$lane.shard")" "$GO" "$(basename "$OLDRUN")" "$BRANCH" "$BENID" "$BENNAME" "$BEN_PORT" "$CONFNAME" "$BENCOMMIT" "$W" 2>/dev/null <<'PYEOF'
import hashlib, json, os, platform, sys, time
run, box, lane, shard, go, capsule, branch, benid, benname, port, confname, bencommit, w = sys.argv[1:14]
import numpy, scipy, tensorflow as tf
cpu = next((l.split(':', 1)[1].strip() for l in open('/proc/cpuinfo') if l.lower().startswith('model name')), None)
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
json.dump(dict(host=box, machine='Azure Standard_F8as_v6, 8 vCPUs, 32 GB', cpu=cpu, os=platform.platform(), python=sys.version.split()[0],
    packages=dict(tensorflow=tf.__version__, numpy=numpy.__version__, scipy=scipy.__version__),
    source_repository='https://github.com/maxschireson/Single-Dummy-Bridge', source_branch='feature/gen7-selfplay-20261112', source_commit=go, generation='Gen 7.1: 71s-32 is 7s-32 with policy net v4.1',
    source_run=f"this lane's drained Gen 7.0 cohort {capsule}: the deals it had not played (originally sub-shard {shard} of the capture capsule)",
    plan='configs/round71-ben.json reduced to the pair 71s-32~' + benid + ' (plan.json beside this file)',
    shard=shard, lane=int(lane), workers='the runtime\'s single BEN worker; the normal pool has no pair to play',
    threads='one BLAS, OpenMP and TensorFlow thread a process', publication_branch=branch,
    supervision=f'systemd units benlane-netns@{lane}, ben-server@{lane}, arena-ben@{lane} and arena-ben-publish@{lane}; the server and the collector '
                f'share the private network namespace benlane-{lane}, so each lane on this machine has its own BEN server at 127.0.0.1:{port}',
    operator='Claude session https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ, through the boxctl agent (docs/boxctl.md)'),
    open(os.path.join(run, 'environment.json'), 'w'), indent=1)
json.dump(dict(launched_epoch=time.time(),
    authority='Max, 12 November 2026, 05:42 UTC: push 7.1 from 06:00 UTC unless revoked; all matches other than the 7.0/7.1 comparison replace 7 with 7.1. The BEN lanes are his instruction of 03:26 UTC',
    notice='docs/gen71_2026-11-12.md on feature/gen7-selfplay-20261112', steps='prepare from the drained 7.0 lane cohort, preflight inside the lane, start', host=box, lane=int(lane), shard=shard),
    open(os.path.join(run, 'launch.json'), 'w'), indent=1)
prov = json.load(open(os.path.join(w, 'sdb-gen7-arena/configs/ben-gen5-16.provenance.json')))
models = {}
for m in prov['model_sha256'].values():
    models[m['path']] = sha(os.path.join(w, 'ben', m['path']))
assert all(models[m['path']] == m['sha256'] for m in prov['model_sha256'].values()), 'BEN model files differ from the provenance file'
conf = os.path.join(run, 'assets', confname)
json.dump(dict(bot=benid, label=benname, source='https://github.com/lorserker/ben', source_commit=bencommit,
    config='assets/' + confname, config_sha256=sha(conf), url=f'http://127.0.0.1:{port}',
    model_sha256=models, models_verified_against='configs/ben-gen5-16.provenance.json at ' + go + ' (the BEN (64) profile uses the same model files)',
    python_packages='configs/ben-round5-runtime-requirements.txt at ' + go + ', installed in a venv of its own with no difference from that list',
    packages=[l.strip() for l in open(os.path.join(w, 'ben-setup/ben-venv-freeze.txt')) if l.strip()],
    start=f'cd ben && python src/gameapi.py --config RUN/assets/{confname} --host 127.0.0.1 --port {port} --record false, one BLAS, OpenMP and TensorFlow thread',
    server_check='gameapi.py 0.9.0.2, DDS 3.1.0 with one thread, 17 models warmed up; a bid request answered with who=NN'),
    open(os.path.join(run, 'ben-recovery.json'), 'w'), indent=1)
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
}

cmd_start() {
  local lane=$1; names "$lane"
  sudo systemctl enable --now "arena-ben@$lane.service" >/dev/null 2>&1 || true
  sudo systemctl enable --now "arena-ben-publish@$lane.service" >/dev/null 2>&1 || true
  say "lane $lane: collector $(systemctl is-active "arena-ben@$lane"), publisher $(systemctl is-active "arena-ben-publish@$lane"), feed $BRANCH"
}

cmd_status() {
  "$PY" - "$W" "$BOX" "$LABEL" "$BENID" <<'PYEOF'
import glob, gzip, json, os, subprocess, sys, time
w, box, label, benid = sys.argv[1:5]
unit = lambda n: subprocess.run(['systemctl', 'is-active', n], capture_output=True, text=True).stdout.strip()
now = time.time(); total = 0; recent = 0
for run in sorted(glob.glob(f'{w}/runs/gen71-{box}-{label}-*'), key=lambda p: int(p.rsplit('-', 1)[1])):
    lane = run.rsplit('-', 1)[1]
    rs = [json.load(open(p)) for p in glob.glob(run + '/receipts/*.json')]
    x = [r['imps'] for r in rs]; total += len(rs); r30 = sum(r['completed_epoch'] > now - 1800 for r in rs); recent += r30
    samples = None
    eps = sorted(glob.glob(run + '/episodes/*.json.gz'))
    if eps:
        d = json.load(gzip.open(eps[-1], 'rt'))
        got = [a.get('reported_samples') for e in d['unique_tables'].values() for t in e['tables'] for a in t['actions'] if a.get('engine') == 'BEN' or a.get('reported_samples') is not None]
        got = [g for g in got if g is not None]
        samples = max(got) if got else None
    try: pub = json.load(open(run + '/publisher-status.json')); pub = f"{pub.get('status')} {pub.get('completed')} ({round(now - pub['epoch'])}s ago)"
    except Exception: pub = 'no status yet'
    print(f"lane {lane}: server {unit('ben-server@' + lane)}, collector {unit('arena-ben@' + lane)}, publisher {unit('arena-ben-publish@' + lane)} [{pub}], "
          f"boards {len(rs)} (last 30 min {r30}), IMPs {sum(x):+d}, failures {sorted(os.listdir(run + '/failures'))}, most BEN samples in the latest board {samples}")
print(f"{box} {label}: {total} boards over all lanes; {recent} in the last 30 minutes")
PYEOF
  free -g | awk 'NR==2 {print "memory: used " $3 " GB, available " $7 " GB"}'; uptime | sed 's/.*load/load/'
}

cmd=$1; shift
"cmd_$cmd" "$@"
EOF_LANE71_SH
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
cat > "$L/switch71.sh" <<'EOF_SWITCH71_SH'
#!/usr/bin/env bash
# Move this box's eight BEN lanes from Gen 7.0 to Gen 7.1 (Max, 12 November 2026, 05:42 UTC). The BEN servers keep running.
set -uo pipefail
W=$HOME/work; L=$W/lanes; . "$L/role.env"
say() { echo "$(date -u +%T) $*"; }
LANES="1 2 3 4 5 6 7 8"
say "== build the Gen 7.1 source"
bash "$W/gen71/gen71.sh" build || exit 1
say "== finish the 7.0 lanes"
bash "$L/drain70.sh" || exit 1
say "== Gen 7.1 lanes"
bash "$L/lane71.sh" units || exit 1
bash "$L/lane71.sh" plan || exit 1
for n in $LANES; do bash "$L/lane71.sh" prepare "$n" || exit 1; done
for n in $LANES; do (bash "$L/lane71.sh" preflight "$n" > "$L/$n.pf71.out" 2>&1; echo $? > "$L/$n.pf71.rc") & done
wait
bad=0
for n in $LANES; do cut -c1-330 "$L/$n.pf71.out"; [ "$(cat "$L/$n.pf71.rc")" = 0 ] || bad=$((bad+1)); done
[ "$bad" -eq 0 ] || { say "preflights failed: $bad; no lane started"; exit 1; }
for n in $LANES; do bash "$L/lane71.sh" records "$n" && bash "$L/lane71.sh" start "$n"; done
sed -i 's|    R=$W/runs/gen7-phase1-$BOX-$LABEL-$n|    R=$(. "$L/$n.env"; echo "$RUN")|' "$L/recycle.sh"
grep -q 'R=$(. "$L/$n.env"; echo "$RUN")' "$L/recycle.sh" || say "WARNING: the memory supervisor was not pointed at the new runs"
rm -f "$L/RECYCLE_OFF"; sudo systemctl enable --now lane-recycle >/dev/null 2>&1
sleep 90
bash "$L/lane71.sh" status
say "lane-recycle $(systemctl is-active lane-recycle)"
say DONE
EOF_SWITCH71_SH
chmod +x "$S/gen71.sh" "$L/lane71.sh" "$L/drain70.sh" "$L/switch71.sh"
systemctl is-active --quiet switch71 && { echo "already running"; exit 0; }
sudo systemctl reset-failed switch71 2>/dev/null || true
sudo systemd-run --quiet --unit=switch71 --uid="$(id -un)" --setenv=HOME="$HOME" \
  --property=StandardOutput=append:"$L/switch71.log" --property=StandardError=append:"$L/switch71.log" -- "$L/switch71.sh"
sleep 20; echo "switch71: $(systemctl is-active switch71)"; tail -4 "$L/switch71.log" | cut -c1-240
