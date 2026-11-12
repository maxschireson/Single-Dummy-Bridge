# boxctl: timeout=60
# azure3: prepare the next pool for the eight Gen 7.1 BEN (64) lanes while they play: eight cohorts from the drained phase 1
# cohort gen7-phase1-azure3, its unplayed deals without the v4.1 training families, one eighth each; preflight each inside its
# lane; then unit lane-switch moves a lane over when its current cohort has played all its deals. Background unit prepnext;
# progress in ~/work/lanes/prepnext.log.
set -euo pipefail
L=$HOME/work/lanes
[ "$BOXCTL_BOX" = azure3 ] || { echo "this command is for azure3"; exit 1; }
cat > "$L/lane71n.sh" <<'EOF_LANE71N'
#!/usr/bin/env bash
# BEN lanes for Gen 7.1 on this box, next pool: when a lane's current cohort (gen71fresh-BOX-LABEL-N, deals v4.1 was not
# trained on) has played all its deals, the lane goes on with a new cohort prepared from this box's drained Gen 7.0
# phase 1 cohort (gen7-phase1-BOX): its unplayed deals without the families v4.1 was trained on (--exclude-families),
# split eight ways (--shard K/8, lane N takes K = N-1). The cohorts are prepared and preflighted while the current lanes
# play; unit lane-switch moves each lane over when its current cohort is done. The BEN servers keep running.
#
#   lane71n.sh plan | prepare LANE | preflight LANE | records LANE | status
set -euo pipefail
W=$HOME/work; PY=$W/venv/bin/python; SRC=$W/sdb-gen71x; BEN=$W/ben; BV=$W/ben-venv; L=$W/lanes
GO=a588e09e4aec88fa8b41e814df95b515f07e134c
LIST=$W/gen71/all-training-families.json; LISTSHA=4818856d731bee23ea38cf16b478a73106ad06a2116dca046fae8a9098b103e3
BENCOMMIT=9b5f43104aeac713a80b73513f2f2d6daf9f8769
U=$(id -un)
CAPS="OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TF_NUM_INTRAOP_THREADS=1 TF_NUM_INTEROP_THREADS=1 TF_CPP_MIN_LOG_LEVEL=3"
SSH="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
REMOTE=git@github.com:maxschireson/Single-Dummy-Bridge.git
. "$L/role.env"      # BOX, BENID, LABEL, BEN_PORT, CONFNAME, BENNAME
say() { echo "$(date -u +%T) $*"; }
names() { RUN=$W/runs/gen71fresh2-$BOX-$LABEL-$1; PUB=$W/publication/gen71fresh2-$BOX-$LABEL-$1; BRANCH=arena-gen7-1-fresh2-$BOX-$LABEL-$1-feed; OLDRUN=$W/runs/gen7-phase1-$BOX; CUR=$W/runs/gen71fresh-$BOX-$LABEL-$1; SHARD="$(( $1 - 1 ))/8"; }


cmd_plan() {
  [ "$(git -C "$SRC" rev-parse HEAD)" = "$GO" ] || { say "source is not at $GO"; exit 1; }
  "$PY" - "$SRC/configs/round71-ben.json" "$L/plan71n-$LABEL.json" "$BENID" "$BENNAME" "$BOX" <<'PYEOF'
import json, sys
src, dst, benid, benname, box = sys.argv[1:6]
p = json.load(open(src))
assert p['launch_enabled'] is True and not p['pending'], 'the Gen 7.1 BEN plan is not open'
pair = '71s-32~' + benid
assert pair in p['pair_weights'], pair
p['roster'] = ['71s-32', benid]
p['pair_weights'] = {pair: 1}
p['title'] = f'Gen 7.1 · {benname} pair on {box}: standard with policy v4.1 against {benname}, deals v4.1 was not trained on'
p['notes'] = list(p.get('notes', [])) + [
    f"This copy of configs/round71-ben.json keeps one of its two pairs, {pair}: one Azure machine plays each BEN level (Max, 12 November 2026, 03:26 UTC). "
    f"Only the roster, the pair weights, the title and these notes differ from that file.",
    "The cohort is prepared with --exclude-families: no deal from the 32,205 families the policy net v4.1 was trained on (the independent collector's "
    "all-training-families.json, sha256 4818856d731bee23...). Its deals are one eighth (--shard) of the unplayed deals of this machine's Gen 7.0 phase 1 cohort."]
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
  # The source run is this machine's Gen 7.0 phase 1 cohort, stopped for good at 03:50 UTC: STOP, no collector, every board published.
  [ "$(sha256sum "$LIST" | cut -c1-64)" = "$LISTSHA" ] || { say "the list of training families is not the expected file"; exit 1; }
  [ -e "$OLDRUN/STOP" ] || { say "the phase 1 cohort has no STOP file"; exit 1; }
  [ "$(systemctl is-active arena-gen7)" = active ] && { say "the phase 1 collector is running"; exit 1; }
  [ -z "$(ls "$OLDRUN/failures" 2>/dev/null)" ] || { say "the phase 1 cohort has failure records"; exit 1; }
  local played published
  played=$(ls "$OLDRUN/receipts" | wc -l)
  published=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$OLDRUN/publisher-status.json")
  [ "$played" = "$published" ] || { say "the phase 1 feed has $published of $played boards"; exit 1; }
  [ -e "$OLDRUN/WATCHDOG_STOP" ] || echo "Finished for good on 12 November 2026 at 03:50 UTC (the box went to BEN lanes). On $(date -u +%FT%TZ) its unplayed deals not from the families the policy net v4.1 was trained on went to gen71fresh2-$BOX-$LABEL-1 to -8 (one eighth each). No watchdog ran on this box." > "$OLDRUN/WATCHDOG_STOP"
  cd "$SRC"
  "$PY" ops/prepare_gen7_alpha.py --source "$OLDRUN" --run "$RUN" --plan "$L/plan71n-$LABEL.json" --exclude-families "$LIST" --shard "$SHARD" > "$L/$lane.prepare71n.json"
  "$PY" - "$L/$lane.prepare71n.json" "$BENID" "$lane" "$OLDRUN" "$RUN" "$played" "$LIST" "$LISTSHA" "$CUR" "$CONFNAME" <<'PYEOF'
import glob, json, os, sys
sys.path.insert(0, os.getcwd())
from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load
d = json.load(open(sys.argv[1])); benid, lane = sys.argv[2:4]; old = json.load(open(sys.argv[4] + '/manifest.json')); m = json.load(open(sys.argv[5] + '/manifest.json')); played = int(sys.argv[6])
trained = set(json.load(open(sys.argv[7])))
done = {json.load(open(p))['family'] for p in glob.glob(sys.argv[4] + '/receipts/*.json')}
old_fams = [deal_key(b.hands, True) for b in load(os.path.join(sys.argv[4], old['corpus']))]
new_fams = [deal_key(b.hands, True) for b in load(os.path.join(sys.argv[5], m['corpus']))]
k = int(lane) - 1
assert new_fams == [f for f in old_fams if f not in done and f not in trained][k::8], 'the new corpus is not shard k/8 of the old unplayed deals without the training families, in order'
assert not set(new_fams) & trained and len(set(new_fams)) == len(new_fams)
ex = m['evaluation_exclusions']
assert ex['sha256'] == sys.argv[8] and ex['families'] == len(trained), ex
left_out = sum(1 for f in old_fams if f not in done and f in trained)
cur = json.load(open(sys.argv[9] + '/manifest.json'))
assert os.path.exists(os.path.join(sys.argv[5], 'assets', sys.argv[10])), 'the BEN profile is not among the run assets'
tree = d['gen7']['71s-32']['tree'][0]
assert d['allocation'] == {'71s-32~' + benid: 1}, d['allocation']
assert (tree['root_margin'], tree['trust'], tree['path'], tree['tricks']) == (0.25, 0.3, 0.5, 3), 'not the authorized tree settings'
a, b = old['bots']['7s-32'], m['bots']['71s-32']
assert b == cur['bots']['71s-32'], '71s-32 is not the bot of the lane\'s current cohort'
assert m['bots'][benid] == cur['bots'][benid], benid + ' is not the bot of the lane\'s current cohort'
assert m['bots']['7s-32'] == a and {k for k in a if a[k] != b.get(k)} == {'id', 'identity', 'gen7_policy', 'artifact_sha256'}, '71s-32 differs from 7s-32 in more than the net'
assert b['artifact_sha256']['gen7_policy'] == 'cb3fcfd5c55873735ee22ea5e7ba04606794bed38d261fdf3f1b3a4af5c9fbed'
assert m['target'] == len(new_fams) and m['source_generation'] == old['identity'] and m.get('shard') == dict(index=k, of=8), (m['target'], m.get('shard'))
print(f"lane {lane}: cohort {d['identity'][:12]}, {d['target']} deals: shard {k}/8 of the phase 1 cohort {old['identity'][:12]}'s unplayed deals ({played} played, {left_out} unplayed deals from training families left out over all shards), pairs {d['allocation']}, 71s-32 {b['identity'][:12]}, exclusions sha256 {ex['sha256'][:16]}")
PYEOF
  cat > "$L/$lane.next.env" <<ENV
RUN=$RUN
PUB=$PUB
BEN_PORT=$BEN_PORT
BEN_CONF=$RUN/assets/$CONFNAME
XDG_CACHE_HOME=$L/$lane.cache
ENV
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
  cp "$L/plan71n-$LABEL.json" "$RUN/plan.json"
  "$PY" -m pip freeze 2>/dev/null > "$RUN/runtime-requirements.txt"
  env TF_CPP_MIN_LOG_LEVEL=3 "$PY" - "$RUN" "$BOX" "$lane" "$SHARD of the drained phase 1 cohort's unplayed deals without the v4.1 training families" "$GO" "$(basename "$OLDRUN")" "$BRANCH" "$BENID" "$BENNAME" "$BEN_PORT" "$CONFNAME" "$BENCOMMIT" "$W" 2>/dev/null <<'PYEOF'
import hashlib, json, os, platform, sys, time
run, box, lane, shard, go, capsule, branch, benid, benname, port, confname, bencommit, w = sys.argv[1:14]
import numpy, scipy, tensorflow as tf
cpu = next((l.split(':', 1)[1].strip() for l in open('/proc/cpuinfo') if l.lower().startswith('model name')), None)
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
json.dump(dict(host=box, machine='Azure Standard_F8as_v6, 8 vCPUs, 32 GB', cpu=cpu, os=platform.platform(), python=sys.version.split()[0],
    packages=dict(tensorflow=tf.__version__, numpy=numpy.__version__, scipy=scipy.__version__),
    source_repository='https://github.com/maxschireson/Single-Dummy-Bridge', source_branch='codex/gen71-independent-20261112 (feature/gen7-selfplay-20261112 at 9f5ec19 plus the option --exclude-families; engine, runtime and publisher unchanged)', source_commit=go, generation='Gen 7.1: 71s-32 is 7s-32 with policy net v4.1',
    source_run=f"this machine's drained Gen 7.0 phase 1 cohort {capsule}: shard {shard}",
    plan='configs/round71-ben.json reduced to the pair 71s-32~' + benid + ' (plan.json beside this file)',
    shard=shard, lane=int(lane), workers='the runtime\'s single BEN worker; the normal pool has no pair to play',
    threads='one BLAS, OpenMP and TensorFlow thread a process', publication_branch=branch,
    supervision=f'systemd units benlane-netns@{lane}, ben-server@{lane}, arena-ben@{lane} and arena-ben-publish@{lane}; the server and the collector '
                f'share the private network namespace benlane-{lane}, so each lane on this machine has its own BEN server at 127.0.0.1:{port}',
    operator='Claude session https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ, through the boxctl agent (docs/boxctl.md)'),
    open(os.path.join(run, 'environment.json'), 'w'), indent=1)
json.dump(dict(launched_epoch=time.time(),
    authority='Max, 12 November 2026, 05:42 UTC: push 7.1 from 06:00 UTC unless revoked; all matches other than the 7.0/7.1 comparison replace 7 with 7.1. The BEN lanes are his instruction of 03:26 UTC',
    notice='docs/gen71_2026-11-12.md on feature/gen7-selfplay-20261112', reason='the lane\'s previous cohort ran out of deals; this one takes the next pool, leaving out the v4.1 training families',
    steps='prepare from the drained phase 1 cohort with --exclude-families and --shard, preflight inside the lane while the previous cohort played, start by unit lane-switch when it finished', host=box, lane=int(lane), shard=shard),
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


cmd_status() {
  "$PY" - "$W" "$BOX" "$LABEL" "$BENID" <<'PYEOF'
import glob, gzip, json, os, subprocess, sys, time
w, box, label, benid = sys.argv[1:5]
unit = lambda n: subprocess.run(['systemctl', 'is-active', n], capture_output=True, text=True).stdout.strip()
now = time.time(); total = 0; recent = 0
for run in sorted(glob.glob(f'{w}/runs/gen71fresh2-{box}-{label}-*'), key=lambda p: int(p.rsplit('-', 1)[1])):
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
EOF_LANE71N
cat > "$L/laneswitch.sh" <<'EOF_SWITCH'
#!/usr/bin/env bash
# Unit lane-switch: when a lane's current cohort has played all its deals (collector exited, every board published), move the
# lane to the cohort prepared for it in N.next.env and start its collector and publisher. A lane whose collector stopped for
# any other reason (a STOP, a failure record, the memory supervisor) is left alone. ~/work/lanes/SWITCH_OFF switches it off.
set -uo pipefail
W=$HOME/work; L=$W/lanes; PY=$W/venv/bin/python
say() { echo "$(date -u +%FT%TZ) $*"; }
say "started"
while true; do
  for n in 1 2 3 4 5 6 7 8; do
    [ -e "$L/SWITCH_OFF" ] && break
    [ -e "$L/$n.next.env" ] || continue
    R=$(. "$L/$n.env"; echo "$RUN"); N=$(. "$L/$n.next.env"; echo "$RUN")
    [ "$R" != "$N" ] || continue
    [ "$(systemctl is-active "arena-ben@$n")" = active ] && continue
    [ -e "$L/$n.recycling" ] && continue
    t=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['target'])" "$R/manifest.json"); k=$(ls "$R/receipts" | wc -l)
    [ "$k" -ge "$t" ] || continue
    [ -z "$(ls "$R/failures")" ] || { say "lane $n: failure record in $(basename "$R"); not switching"; continue; }
    p=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$R/publisher-status.json" 2>/dev/null)
    [ "$p" = "$k" ] || continue
    say "lane $n: $(basename "$R") done ($k of $t boards, all published); moving to $(basename "$N")"
    touch "$R/STOP" "$R/PUBLISH_STOP"
    for i in $(seq 1 30); do [ "$(systemctl is-active "arena-ben-publish@$n")" = active ] || break; sleep 5; done
    sudo systemctl stop "arena-ben-publish@$n" >/dev/null 2>&1
    [ -e "$R/WATCHDOG_STOP" ] || echo "Finished on $(date -u +%FT%TZ): every deal played and published; the lane went on with $(basename "$N"). No watchdog ran on this box." > "$R/WATCHDOG_STOP"
    cp "$L/$n.env" "$L/$n.env.$(basename "$R")"; mv "$L/$n.next.env" "$L/$n.env"
    sudo systemctl reset-failed "arena-ben@$n" "arena-ben-publish@$n" 2>/dev/null
    sudo systemctl start "arena-ben@$n" "arena-ben-publish@$n"
    say "lane $n: collector $(systemctl is-active "arena-ben@$n"), publisher $(systemctl is-active "arena-ben-publish@$n") on $(basename "$N")"
  done
  sleep 60
done
EOF_SWITCH
cat > "$L/prepnext.sh" <<'EOF_PREP'
#!/usr/bin/env bash
# azure3: prepare the next pool for the eight BEN (64) lanes while they play (lane71n.sh), then install unit lane-switch.
set -uo pipefail
W=$HOME/work; L=$W/lanes
say() { echo "$(date -u +%T) $*"; }
LANES="1 2 3 4 5 6 7 8"
bash "$L/lane71n.sh" plan || exit 1
bash "$L/lane71n.sh" prepare 1 || exit 1
for n in 2 3 4 5 6 7 8; do bash "$L/lane71n.sh" prepare "$n" || exit 1; done
for n in $LANES; do (nice -n 5 bash "$L/lane71n.sh" preflight "$n" > "$L/$n.pf71n.out" 2>&1; echo $? > "$L/$n.pf71n.rc") & done
wait
bad=0
for n in $LANES; do cut -c1-330 "$L/$n.pf71n.out"; [ "$(cat "$L/$n.pf71n.rc")" = 0 ] || bad=$((bad+1)); done
[ "$bad" -eq 0 ] || { say "preflights failed: $bad; next pool not armed"; for n in $LANES; do rm -f "$L/$n.next.env"; done; exit 1; }
for n in $LANES; do bash "$L/lane71n.sh" records "$n" || { say "records failed for lane $n"; exit 1; }; done
sudo tee /etc/systemd/system/lane-switch.service >/dev/null <<UNIT
[Unit]
Description=Move a BEN lane to its next cohort when the current one has played all its deals

[Service]
User=$(id -un)
Environment=HOME=$HOME
ExecStart=$L/laneswitch.sh
StandardOutput=append:$L/laneswitch.log
StandardError=append:$L/laneswitch.log
Restart=always
RestartSec=20

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload; sudo systemctl enable --now lane-switch >/dev/null 2>&1
say "next pool armed: $(for n in $LANES; do echo -n "$n:$(. "$L/$n.next.env"; basename "$RUN") "; done); lane-switch $(systemctl is-active lane-switch)"
say DONE
EOF_PREP
chmod +x "$L/lane71n.sh" "$L/laneswitch.sh" "$L/prepnext.sh"
systemctl is-active --quiet prepnext && { echo "already running"; exit 0; }
sudo systemctl reset-failed prepnext 2>/dev/null || true
sudo systemd-run --quiet --unit=prepnext --uid="$(id -un)" --setenv=HOME="$HOME" \
  --property=StandardOutput=append:"$L/prepnext.log" --property=StandardError=append:"$L/prepnext.log" -- "$L/prepnext.sh"
sleep 40; echo "prepnext: $(systemctl is-active prepnext)"; tail -6 "$L/prepnext.log" | cut -c1-300
