# boxctl: timeout=60
# azure3: the eight BEN (64) lanes go to Gen 8 (Max, 15:32, 15:33, 15:50 and 16:11 UTC): 8s-32~ben64 from each lane's third Gen 7.1 pool,
# without the v4.1 training families (the union list). Background unit switch8; progress in ~/work/lanes/switch8.log.
set -euo pipefail
L=$HOME/work/lanes
[ "$BOXCTL_BOX" = azure3 ] || { echo "this command is for azure3"; exit 1; }
cat > "$L/lane8.sh" <<'EOF_LANE8'
#!/usr/bin/env bash
# BEN lanes for Gen 8 on this box (Max, 12 November 2026, 15:32 "Go ahead", 15:33, 15:50, and 16:11 UTC to the operator:
# switch the arena to Gen 8): configs/round8-candidate-ben.json reduced to its BEN (64) pair, 8s-32~ben64, because this
# machine's eight BEN servers run the BEN (64) profile. Each lane's cohort takes over the deals of the lane's third Gen 7.1
# pool (gen71fresh3-BOX-LABEL-N, capsule shard 6/8; played or not), without the families policy v4.1 was trained on (the
# union of the two lists). Source feature/gen8-prototype-20261112 at 792c4cb. The BEN servers keep running.
#   lane8.sh units | plan | prepare LANE | preflight LANE | records LANE | start LANE | status
set -euo pipefail
W=$HOME/work; PY=$W/venv/bin/python; SRC=$W/sdb-gen8; BEN=$W/ben; BV=$W/ben-venv; L=$W/lanes
GO=792c4cb3f647ec71273f0cc57d95be1d0a0a5954
LIST=$W/gen8/v41-training-families-union.json; LISTSHA=0b8ac2b7f41b91915f518c42f76701728097b4151acb5d0e964051c261eca0e2
BENCOMMIT=9b5f43104aeac713a80b73513f2f2d6daf9f8769
U=$(id -un)
CAPS="OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TF_NUM_INTRAOP_THREADS=1 TF_NUM_INTEROP_THREADS=1 TF_CPP_MIN_LOG_LEVEL=3"
SSH="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
REMOTE=git@github.com:maxschireson/Single-Dummy-Bridge.git
. "$L/role.env"      # BOX, BENID, LABEL, BEN_PORT, CONFNAME, BENNAME
say() { echo "$(date -u +%T) $*"; }
names() { RUN=$W/runs/gen8-$BOX-$LABEL-$1; PUB=$W/publication/gen8-$BOX-$LABEL-$1; BRANCH=arena-gen8-$BOX-$LABEL-$1-feed; OLDRUN=$W/runs/gen71fresh3-$BOX-$LABEL-$1; }

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
Description=Gen 8 collector against $BENNAME, lane %i
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
Description=Gen 8 feed publisher, BEN lane %i
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

SRC = Path.home() / 'work' / 'sdb-gen8'
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
  "$PY" - "$SRC/configs/round8-candidate-ben.json" "$L/plan8-$LABEL.json" "$BENID" "$BENNAME" "$BOX" <<'PYEOF'
import json, sys
src, dst, benid, benname, box = sys.argv[1:6]
p = json.load(open(src))
assert p['launch_enabled'] is True and not p['pending'] and p.get('exclude_training_families') is True, 'the Gen 8 BEN plan is not open'
pair = '8s-32~' + benid
assert pair in p['pair_weights'], pair
p['roster'] = ['8s-32', benid]
p['pair_weights'] = {pair: 1}
p['title'] = f'Gen 8 · {benname} pair on {box}: the candidate against {benname}, deals v4.1 was not trained on'
p['notes'] = list(p.get('notes', [])) + [
    f"This copy of configs/round8-candidate-ben.json keeps one of its two pairs, {pair}: this machine's BEN servers run the {benname} profile. "
    "Only the roster, the pair weights, the title and this note differ from that file."]
if 'systems' in p: p['systems'] = {k: v for k, v in p['systems'].items() if k in p['roster'] or k == p.get('common_bidder')}
json.dump(p, open(dst, 'w'), indent=1)
print('plan:', p['title'], '| pairs', p['pair_weights'], '| systems', p.get('systems'), '| exclude', p.get('exclude_training_families'))
PYEOF
}

cmd_prepare() {
  local lane=$1; names "$lane"
  [ -e "$RUN" ] && { say "$RUN already exists; not overwriting"; exit 1; }
  [ -e "$PUB" ] && { say "$PUB already exists; not overwriting"; exit 1; }
  if GIT_SSH_COMMAND="$SSH" git ls-remote --exit-code --heads "$REMOTE" "$BRANCH" >/dev/null 2>&1; then say "branch $BRANCH already exists on GitHub"; exit 1; fi
  # The source run is this lane's third Gen 7.1 pool (gen71fresh3-...-N): stopped, collector gone, every board it played published.
  [ "$(sha256sum "$LIST" | cut -c1-64)" = "$LISTSHA" ] || { say "the list of training families is not the expected file"; exit 1; }
  [ "$(systemctl is-active "arena-ben@$lane")" = active ] && { say "lane $lane: its collector is still running"; exit 1; }
  [ -e "$OLDRUN/STOP" ] || touch "$OLDRUN/STOP"
  [ -z "$(ls "$OLDRUN/failures" 2>/dev/null)" ] || { say "lane $lane: the 7.1 pool has failure records"; exit 1; }
  local played published
  played=$(ls "$OLDRUN/receipts" | wc -l)
  if [ "$played" -gt 0 ]; then
    published=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$OLDRUN/publisher-status.json")
    [ "$played" = "$published" ] || { say "lane $lane: the 7.1 pool's feed has $published of $played boards"; exit 1; }
  fi
  [ -e "$OLDRUN/WATCHDOG_STOP" ] || echo "Finished for good on $(date -u +%FT%TZ) with $played boards: the arena went to Gen 8 (Max, 15:32 and 16:11 UTC). Its unplayed deals not from the families the policy net v4.1 was trained on went to $(basename "$RUN"). No watchdog ran on this box." > "$OLDRUN/WATCHDOG_STOP"
  cd "$SRC"
  "$PY" ops/prepare_gen7_alpha.py --source "$OLDRUN" --run "$RUN" --plan "$L/plan8-$LABEL.json" --exclude-families "$LIST" > "$L/$lane.prepare8.json"
  "$PY" - "$L/$lane.prepare8.json" "$BENID" "$lane" "$OLDRUN" "$RUN" "$played" "$LIST" "$LISTSHA" <<'PYEOF'
import glob, json, os, sys
sys.path.insert(0, os.getcwd())
from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load
d = json.load(open(sys.argv[1])); benid, lane = sys.argv[2:4]; old = json.load(open(sys.argv[4] + '/manifest.json')); m = json.load(open(sys.argv[5] + '/manifest.json')); played = int(sys.argv[6])
trained = set(json.load(open(sys.argv[7])))
done = {json.load(open(p))['family'] for p in glob.glob(sys.argv[4] + '/receipts/*.json')}
old_fams = [deal_key(b.hands, True) for b in load(os.path.join(sys.argv[4], old['corpus']))]
new_fams = [deal_key(b.hands, True) for b in load(os.path.join(sys.argv[5], m['corpus']))]
assert new_fams == [f for f in old_fams if f not in done and f not in trained], 'the new corpus is not the old unplayed deals without the training families, in order'
assert not set(new_fams) & trained and len(set(new_fams)) == len(new_fams)
ex = m['evaluation_exclusions']
assert ex['sha256'] == sys.argv[8] and ex['families'] == len(trained), ex
left_out = sum(1 for f in old_fams if f not in done and f in trained)
assert d['allocation'] == {'8s-32~' + benid: 1}, d['allocation']
b = m['bots']['8s-32']
assert b['identity'].startswith('269fdf1854f4'), ('8s-32', b['identity'][:12])
assert m['bots'][benid] == old['bots'][benid], benid + ' is not the bot of the lane\'s 7.1 pool'
assert b['artifact_sha256']['gen7_policy'] == 'cb3fcfd5c55873735ee22ea5e7ba04606794bed38d261fdf3f1b3a4af5c9fbed'
assert m['target'] == old['target'] - played - left_out == len(new_fams) and m['source_generation'] == old['identity']
print(f"lane {lane}: cohort {d['identity'][:12]}, {d['target']} deals taken over from the lane's 7.1 pool {old['identity'][:12]} ({played} played, {left_out} unplayed deals from training families left out), pairs {d['allocation']}, 8s-32 {b['identity'][:12]}, systems {m.get('systems')}, exclusions {ex['families']} families, sha256 {ex['sha256'][:16]}")
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
  cp "$L/plan8-$LABEL.json" "$RUN/plan.json"
  "$PY" -m pip freeze 2>/dev/null > "$RUN/runtime-requirements.txt"
  env TF_CPP_MIN_LOG_LEVEL=3 "$PY" - "$RUN" "$BOX" "$lane" "the lane's third Gen 7.1 pool (an eighth of capsule shard 6/8) without the v4.1 training families" "$GO" "$(basename "$OLDRUN")" "$BRANCH" "$BENID" "$BENNAME" "$BEN_PORT" "$CONFNAME" "$BENCOMMIT" "$W" 2>/dev/null <<'PYEOF'
import hashlib, json, os, platform, sys, time
run, box, lane, shard, go, capsule, branch, benid, benname, port, confname, bencommit, w = sys.argv[1:14]
import numpy, scipy, tensorflow as tf
cpu = next((l.split(':', 1)[1].strip() for l in open('/proc/cpuinfo') if l.lower().startswith('model name')), None)
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
json.dump(dict(host=box, machine='Azure Standard_F8as_v6, 8 vCPUs, 32 GB', cpu=cpu, os=platform.platform(), python=sys.version.split()[0],
    packages=dict(tensorflow=tf.__version__, numpy=numpy.__version__, scipy=scipy.__version__),
    source_repository='https://github.com/maxschireson/Single-Dummy-Bridge', source_branch='feature/gen8-prototype-20261112', source_commit=go, generation='Gen 8 candidate 8s-32 against BEN',
    source_run=f"this lane's Gen 7.1 pool {capsule}: the deals it had not played, without the families the policy net v4.1 was trained on (the union of the two lists; artifacts/validation/evaluation-exclusions.json)",
    plan='configs/round8-candidate-ben.json reduced to the pair 8s-32~' + benid + ' (plan.json beside this file)',
    shard=shard, lane=int(lane), workers='the runtime\'s single BEN worker; the normal pool has no pair to play',
    threads='one BLAS, OpenMP and TensorFlow thread a process', publication_branch=branch,
    supervision=f'systemd units benlane-netns@{lane}, ben-server@{lane}, arena-ben@{lane} and arena-ben-publish@{lane}; the server and the collector '
                f'share the private network namespace benlane-{lane}, so each lane on this machine has its own BEN server at 127.0.0.1:{port}',
    operator='Claude session https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ, through the boxctl agent (docs/boxctl.md)'),
    open(os.path.join(run, 'environment.json'), 'w'), indent=1)
json.dump(dict(launched_epoch=time.time(),
    authority='Max, 12 November 2026, 15:32 UTC Go ahead (Gen 8); 15:33 machines on Gen 7 work switch to the Gen 8 arena; 15:50 never a board in a training family; 16:11 to the operator: switch the arena to Gen 8. The BEN lanes are his instruction of 03:26 UTC',
    notice='docs/gen8_candidate_2026-11-12.md on feature/gen8-prototype-20261112', reason='the arena goes to Gen 8',
    steps='prepare from the lane\'s Gen 7.1 pool with --exclude-families, preflight inside the lane, start', host=box, lane=int(lane), shard=shard),
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
for run in sorted(glob.glob(f'{w}/runs/gen8-{box}-{label}-*'), key=lambda p: int(p.rsplit('-', 1)[1])):
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
EOF_LANE8
cat > "$L/switch8.sh" <<'EOF_SWITCH8'
#!/usr/bin/env bash
# azure3: the eight BEN (64) lanes go from Gen 7.1 to Gen 8 (Max, 15:32, 15:33, 15:50 and 16:11 UTC). Build the Gen 8 source while
# the lanes play; then stop the lane switcher and the memory supervisor, finish every lane's running cohort (boards in hand
# played out, every board published), prepare each lane's Gen 8 cohort from its third Gen 7.1 pool without the v4.1 training
# families, preflight inside each lane, start. The BEN servers keep running. Nothing is deleted.
set -uo pipefail
W=$HOME/work; L=$W/lanes; PY=$W/venv/bin/python; SRC=$W/sdb-gen8; . "$L/role.env"
COMMIT=792c4cb3f647ec71273f0cc57d95be1d0a0a5954
say() { echo "$(date -u +%T) $*"; }
LANES="1 2 3 4 5 6 7 8"
mkdir -p $W/gen8; LIST=$W/gen8/v41-training-families-union.json
[ -s "$LIST" ] || curl -fsS --max-time 120 -o "$LIST" https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/fccbbd80504272151e298799878bdd37db632c47/v41-training-families-union.json
[ "$(sha256sum "$LIST" | cut -c1-64)" = 0b8ac2b7f41b91915f518c42f76701728097b4151acb5d0e964051c261eca0e2 ] || { say "the list of training families is not the expected file"; exit 1; }
say "== build the Gen 8 source (the lanes keep playing)"
if [ ! -d "$SRC/.git" ]; then git init -q "$SRC" && git -C "$SRC" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; fi
git -C "$SRC" fetch -q --depth 30 origin feature/gen8-prototype-20261112 && git -C "$SRC" checkout -q "$COMMIT" || { say "could not check out $COMMIT"; exit 1; }
cd "$SRC"
for r in models/*/*/restore*.py; do (cd "$(dirname "$r")" && "$PY" "$(basename "$r")" >/dev/null 2>/tmp/restore.err) || say "FAILED $r: $(tail -1 /tmp/restore.err)"; done
"$PY" scripts/build_dds.py >/dev/null 2>&1 || true
[ -s bridge_harness/libbridge_dds.so ] || { say "DDS library was not built"; exit 1; }
CAPS="OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TF_NUM_INTRAOP_THREADS=1 TF_NUM_INTEROP_THREADS=1 TF_CPP_MIN_LOG_LEVEL=3"
for pattern in "test_gen8*.py" "test_rule_bidder.py" "test_bidding_systems.py"; do
  out=$(env $CAPS nice -n 5 "$PY" -m unittest discover -s tests -p "$pattern" 2>&1 | grep -E "^(Ran|OK|FAILED|ERROR:|FAIL:)" | tr '\n' ' ' | cut -c1-400)
  say "tests $pattern: $out"; case "$out" in *" OK"*) ;; *) say "the Gen 8 tests did not pass"; exit 1;; esac
done
say "checkout $(git rev-parse --short HEAD); system scorer $(sha256sum models/cardplay/gen8-system-scorer-v1-2026-11-12/*.npz 2>/dev/null | head -1 | cut -c1-16)"
say "== finish the Gen 7.1 lanes"
touch "$L/SWITCH_OFF"; sudo systemctl disable --now lane-switch >/dev/null 2>&1
touch "$L/RECYCLE_OFF"; for i in $(seq 1 120); do ls "$L"/*.recycling >/dev/null 2>&1 || break; sleep 5; done
sudo systemctl disable --now lane-recycle >/dev/null 2>&1
for n in $LANES; do R=$(. "$L/$n.env"; echo "$RUN"); touch "$R/STOP"; done
a=8; for i in $(seq 1 240); do a=0; for n in $LANES; do [ "$(systemctl is-active arena-ben@$n)" = active ] && a=$((a+1)); done; [ "$a" -eq 0 ] && break; sleep 5; done
[ "$a" -eq 0 ] || { say "collectors still running after 20 minutes: $a"; exit 1; }
behind=8
for i in $(seq 1 60); do
  behind=0
  for n in $LANES; do R=$(. "$L/$n.env"; echo "$RUN"); k=$(ls "$R/receipts" | wc -l); p=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$R/publisher-status.json" 2>/dev/null); [ "$p" = "$k" ] || behind=$((behind+1)); done
  [ "$behind" -eq 0 ] && break; sleep 10
done
[ "$behind" -eq 0 ] || { say "feeds still behind after 10 minutes: $behind"; exit 1; }
for n in $LANES; do
  R=$(. "$L/$n.env"; echo "$RUN"); touch "$R/PUBLISH_STOP"
  [ -z "$(ls "$R/failures")" ] || { say "lane $n: failure record in $(basename "$R")"; exit 1; }
  [ -e "$R/WATCHDOG_STOP" ] || echo "Finished for good on $(date -u +%FT%TZ): the arena went to Gen 8. No watchdog ran on this box." > "$R/WATCHDOG_STOP"
done
for i in $(seq 1 30); do a=0; for n in $LANES; do [ "$(systemctl is-active arena-ben-publish@$n)" = active ] && a=$((a+1)); done; [ "$a" -eq 0 ] && break; sleep 5; done
for n in $LANES; do sudo systemctl stop "arena-ben-publish@$n" >/dev/null 2>&1; R=$(. "$L/$n.env"; echo "$RUN"); echo "   lane $n: $(basename "$R") finished at $(ls "$R/receipts" | wc -l) boards"; cp "$L/$n.env" "$L/$n.env.$(basename "$R")"; rm -f "$L/$n.next.env"; done
say "== Gen 8 lanes"
bash "$L/lane8.sh" units || exit 1
bash "$L/lane8.sh" plan || exit 1
for n in $LANES; do bash "$L/lane8.sh" prepare "$n" || exit 1; done
for n in $LANES; do (bash "$L/lane8.sh" preflight "$n" > "$L/$n.pf8.out" 2>&1; echo $? > "$L/$n.pf8.rc") & done
wait
bad=0
for n in $LANES; do cut -c1-330 "$L/$n.pf8.out"; [ "$(cat "$L/$n.pf8.rc")" = 0 ] || bad=$((bad+1)); done
[ "$bad" -eq 0 ] || { say "preflights failed: $bad; no lane started"; exit 1; }
for n in $LANES; do bash "$L/lane8.sh" records "$n" && bash "$L/lane8.sh" start "$n"; done
rm -f "$L/RECYCLE_OFF"; sudo systemctl enable --now lane-recycle >/dev/null 2>&1
sleep 90
bash "$L/lane8.sh" status
say "lane-recycle $(systemctl is-active lane-recycle); lane-switch $(systemctl is-active lane-switch) (off)"
say DONE
EOF_SWITCH8
chmod +x "$L/lane8.sh" "$L/switch8.sh"
systemctl is-active --quiet switch8 && { echo "already running"; exit 0; }
sudo systemctl reset-failed switch8 2>/dev/null || true
sudo systemd-run --quiet --unit=switch8 --uid="$(id -un)" --setenv=HOME="$HOME" \
  --property=StandardOutput=append:"$L/switch8.log" --property=StandardError=append:"$L/switch8.log" -- "$L/switch8.sh"
sleep 20; echo "switch8: $(systemctl is-active switch8)"; tail -4 "$L/switch8.log" | cut -c1-240
