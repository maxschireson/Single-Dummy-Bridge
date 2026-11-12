# boxctl: timeout=60
# azure3: the BEN (64) lanes' third pool, capsule shard 6/8 without the v4.1 training families (claimed on the board). Background unit
# prepnext3; progress in ~/work/lanes/prepnext3.log. lane-switch (already running) moves each lane when its second pool is played out.
set -euo pipefail
L=$HOME/work/lanes
[ "$BOXCTL_BOX" = azure3 ] || { echo "this command is for azure3"; exit 1; }
cat > "$L/lane71p3.sh" <<'EOF_P3'
#!/usr/bin/env bash
# BEN lanes for Gen 7.1 on this box, third pool: shard 6/8 of the capture capsule's unplayed deals (claimed on the board;
# cut exactly as the phase 1 shards were, through the never-played cohort gen71-claim6-BOX), without the families the policy
# net v4.1 was trained on, split eight ways (lane N takes every eighth, starting at N-1). Prepared and preflighted while the
# second-pool lanes play; unit lane-switch moves each lane when its current cohort has played all its deals.
#
#   lane71p3.sh prepare LANE | preflight LANE | records LANE | status
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
names() { RUN=$W/runs/gen71fresh3-$BOX-$LABEL-$1; PUB=$W/publication/gen71fresh3-$BOX-$LABEL-$1; BRANCH=arena-gen7-1-fresh3-$BOX-$LABEL-$1-feed; OLDRUN=$W/runs/gen71-claim6-$BOX; CUR=$W/runs/gen71fresh2-$BOX-$LABEL-$1; SHARD="$(( $1 - 1 ))/8"; }



cmd_prepare() {
  local lane=$1; names "$lane"
  [ -e "$RUN" ] && { say "$RUN already exists; not overwriting"; exit 1; }
  [ -e "$PUB" ] && { say "$PUB already exists; not overwriting"; exit 1; }
  if GIT_SSH_COMMAND="$SSH" git ls-remote --exit-code --heads "$REMOTE" "$BRANCH" >/dev/null 2>&1; then say "branch $BRANCH already exists on GitHub"; exit 1; fi
  # The source run is the never-played claim cohort gen71-claim6-BOX (STOP and WATCHDOG_STOP written by prepnext3.sh).
  [ "$(sha256sum "$LIST" | cut -c1-64)" = "$LISTSHA" ] || { say "the list of training families is not the expected file"; exit 1; }
  [ -e "$OLDRUN/STOP" ] && [ -e "$OLDRUN/WATCHDOG_STOP" ] || { say "the claim cohort is not closed"; exit 1; }
  [ -z "$(ls "$OLDRUN/receipts" 2>/dev/null)" ] || { say "the claim cohort has boards; it should never have been played"; exit 1; }
  local played=0
  cd "$SRC"
  "$PY" ops/prepare_gen7_alpha.py --source "$OLDRUN" --run "$RUN" --plan "$L/plan71n-$LABEL.json" --exclude-families "$LIST" --shard "$SHARD" > "$L/$lane.prepare71p3.json"
  "$PY" - "$L/$lane.prepare71p3.json" "$BENID" "$lane" "$OLDRUN" "$RUN" "$played" "$LIST" "$LISTSHA" "$CUR" "$CONFNAME" <<'PYEOF'
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
b = m['bots']['71s-32']
assert b == cur['bots']['71s-32'], '71s-32 is not the bot of the lane\'s current cohort'
assert m['bots'][benid] == cur['bots'][benid], benid + ' is not the bot of the lane\'s current cohort'
assert b['artifact_sha256']['gen7_policy'] == 'cb3fcfd5c55873735ee22ea5e7ba04606794bed38d261fdf3f1b3a4af5c9fbed'
assert m['target'] == len(new_fams) and m['source_generation'] == old['identity'] and m.get('shard') == dict(index=k, of=8), (m['target'], m.get('shard'))
print(f"lane {lane}: cohort {d['identity'][:12]}, {d['target']} deals: shard {k}/8 of the claim cohort {old['identity'][:12]} (capsule shard 6/8; {left_out} deals from training families left out over all eight), pairs {d['allocation']}, 71s-32 {b['identity'][:12]}, exclusions sha256 {ex['sha256'][:16]}")
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
  env TF_CPP_MIN_LOG_LEVEL=3 "$PY" - "$RUN" "$BOX" "$lane" "$SHARD of capsule shard 6/8 without the v4.1 training families" "$GO" "$(basename "$OLDRUN")" "$BRANCH" "$BENID" "$BENNAME" "$BEN_PORT" "$CONFNAME" "$BENCOMMIT" "$W" 2>/dev/null <<'PYEOF'
import hashlib, json, os, platform, sys, time
run, box, lane, shard, go, capsule, branch, benid, benname, port, confname, bencommit, w = sys.argv[1:14]
import numpy, scipy, tensorflow as tf
cpu = next((l.split(':', 1)[1].strip() for l in open('/proc/cpuinfo') if l.lower().startswith('model name')), None)
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
json.dump(dict(host=box, machine='Azure Standard_F8as_v6, 8 vCPUs, 32 GB', cpu=cpu, os=platform.platform(), python=sys.version.split()[0],
    packages=dict(tensorflow=tf.__version__, numpy=numpy.__version__, scipy=scipy.__version__),
    source_repository='https://github.com/maxschireson/Single-Dummy-Bridge', source_branch='codex/gen71-independent-20261112 (feature/gen7-selfplay-20261112 at 9f5ec19 plus the option --exclude-families; engine, runtime and publisher unchanged)', source_commit=go, generation='Gen 7.1: 71s-32 is 7s-32 with policy net v4.1',
    source_run=f"the claim cohort {capsule} (shard 6/8 of the capture capsule's unplayed deals, never played): {shard}",
    plan='configs/round71-ben.json reduced to the pair 71s-32~' + benid + ' (plan.json beside this file)',
    shard=shard, lane=int(lane), workers='the runtime\'s single BEN worker; the normal pool has no pair to play',
    threads='one BLAS, OpenMP and TensorFlow thread a process', publication_branch=branch,
    supervision=f'systemd units benlane-netns@{lane}, ben-server@{lane}, arena-ben@{lane} and arena-ben-publish@{lane}; the server and the collector '
                f'share the private network namespace benlane-{lane}, so each lane on this machine has its own BEN server at 127.0.0.1:{port}',
    operator='Claude session https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ, through the boxctl agent (docs/boxctl.md)'),
    open(os.path.join(run, 'environment.json'), 'w'), indent=1)
json.dump(dict(launched_epoch=time.time(),
    authority='Max, 12 November 2026, 05:42 UTC: push 7.1 from 06:00 UTC unless revoked; all matches other than the 7.0/7.1 comparison replace 7 with 7.1. The BEN lanes are his instruction of 03:26 UTC',
    notice='docs/gen71_2026-11-12.md on feature/gen7-selfplay-20261112', reason='the lane\'s previous cohort ran out of deals; this one takes the third pool (capsule shard 6/8, claimed on the board), leaving out the v4.1 training families',
    steps='prepare from the claim cohort with --exclude-families and --shard, preflight inside the lane while the previous cohort played, start by unit lane-switch when it finished', host=box, lane=int(lane), shard=shard),
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
for run in sorted(glob.glob(f'{w}/runs/gen71fresh3-{box}-{label}-*'), key=lambda p: int(p.rsplit('-', 1)[1])):
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
EOF_P3
cat > "$L/prepnext3.sh" <<'EOF_PREP3'
#!/usr/bin/env bash
# azure3: the BEN (64) lanes' third pool. Cut capsule shard 6/8 as the phase 1 shards were (cohort gen71-claim6-BOX, never
# played), check it is disjoint from shards 0 to 5, then one lane cohort an eighth of it without the v4.1 training families,
# preflight each inside its lane, records, and arm lane-switch (N.next.env).
set -uo pipefail
W=$HOME/work; L=$W/lanes; PY=$W/venv/bin/python; SRC=$W/sdb-gen71x; . "$L/role.env"
CAP=$W/capsule-gen7-capture/recovery; A=$W/runs/gen71-claim6-$BOX
say() { echo "$(date -u +%T) $*"; }
LANES="1 2 3 4 5 6 7 8"
for n in $LANES; do [ -e "$L/$n.next.env" ] && { say "lane $n already has a next cohort armed"; exit 1; }; done
cd "$SRC"
if [ ! -e "$A" ]; then
  "$PY" ops/prepare_gen7_alpha.py --source "$CAP" --run "$A" --plan "$L/plan71n-$LABEL.json" --shard 6/8 > "$L/prepare-claim6.json" || { say "prepare of the claim cohort failed"; exit 1; }
fi
touch "$A/STOP"
[ -e "$A/WATCHDOG_STOP" ] || echo "Never played. Prepared on $(date -u +%FT%TZ) to cut shard 6/8 of the capture capsule's unplayed deals exactly as the phase 1 shards were; its deals not from the families the policy net v4.1 was trained on went to gen71fresh3-$BOX-$LABEL-1 to -8, an eighth each." > "$A/WATCHDOG_STOP"
"$PY" - "$CAP" "$A" "$W" <<'PYEOF' || exit 1
import glob, json, os, sys
sys.path.insert(0, os.getcwd())
from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load
cap, a, w = sys.argv[1:4]
fam = lambda run: [deal_key(x.hands, True) for x in load(os.path.join(run, json.load(open(run + '/manifest.json'))['corpus']))]
mc = json.load(open(cap + '/manifest.json')); cf = fam(cap); done = {json.load(open(p))['index'] for p in glob.glob(cap + '/receipts/*.json')}
U = [cf[i] for i in range(mc['target']) if i not in done]
af = fam(a)
assert af == U[6::8], 'the claim cohort is not shard 6/8 of the capsule'
for k in (0, 1, 2, 3, 4, 5, 7): assert not set(af) & set(U[k::8]), k
mine = set()
for run in glob.glob(w + '/runs/gen71fresh*'):
    try: mine |= set(fam(run))
    except Exception: pass
assert not set(af) & mine, 'overlap with this box\\'s earlier Gen 7.1 lanes'
print(f"claim cohort {json.load(open(a + '/manifest.json'))['identity'][:12]}: shard 6/8 of capsule {mc['identity'][:12]}, {len(af)} deals, disjoint from the other shards and from this box's earlier lanes")
PYEOF
for n in $LANES; do bash "$L/lane71p3.sh" prepare "$n" || exit 1; done
for n in $LANES; do (nice -n 5 bash "$L/lane71p3.sh" preflight "$n" > "$L/$n.pf71p3.out" 2>&1; echo $? > "$L/$n.pf71p3.rc") & done
wait
bad=0
for n in $LANES; do cut -c1-330 "$L/$n.pf71p3.out"; [ "$(cat "$L/$n.pf71p3.rc")" = 0 ] || bad=$((bad+1)); done
[ "$bad" -eq 0 ] || { say "preflights failed: $bad; third pool not armed"; for n in $LANES; do rm -f "$L/$n.next.env"; done; exit 1; }
for n in $LANES; do bash "$L/lane71p3.sh" records "$n" || { say "records failed for lane $n"; exit 1; }; done
say "third pool armed: $(for n in $LANES; do echo -n "$n:$(. "$L/$n.next.env"; basename "$RUN") "; done); lane-switch $(systemctl is-active lane-switch)"
say DONE
EOF_PREP3
chmod +x "$L/lane71p3.sh" "$L/prepnext3.sh"
systemctl is-active --quiet prepnext3 && { echo "already running"; exit 0; }
sudo systemctl reset-failed prepnext3 2>/dev/null || true
sudo systemd-run --quiet --unit=prepnext3 --uid="$(id -un)" --setenv=HOME="$HOME" \
  --property=StandardOutput=append:"$L/prepnext3.log" --property=StandardError=append:"$L/prepnext3.log" -- "$L/prepnext3.sh"
sleep 50; echo "prepnext3: $(systemctl is-active prepnext3)"; tail -6 "$L/prepnext3.log" | cut -c1-330
