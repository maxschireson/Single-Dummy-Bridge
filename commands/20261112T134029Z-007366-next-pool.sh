# boxctl: timeout=60
# azure1: prepare and arm the next Gen 7.1 cohort (shard 5/8 of the capture capsule without the v4.1 training families) while the
# current one plays; unit mixswitch moves the collector over when the current cohort has played all its deals. Background unit
# go71e; progress in ~/work/gen71/go71e.log.
set -euo pipefail
S=$HOME/work/gen71
[ "$BOXCTL_BOX" = azure1 ] || { echo "this command is for azure1"; exit 1; }
cat > "$S/gen71e.sh" <<'EOF_GEN71E'
#!/usr/bin/env bash
# Gen 7.1 self-play and Gen 7.1 against Gen 7.0 on this box, one board in two each (Max, 12 November 2026, 11:36 UTC,
# of azure1 and azure4: "Yes yes those two boxes for gen 7.1 self play and 7.1 vs 7"). The cohort takes over the unplayed
# deals of this box's drained Gen 7.0 phase 1 cohort (OLD in gen71d.env) without the families the policy net v4.1 was
# trained on (--exclude-families; the independent collector's list, 32,205 families).
#
#   gen71e.sh build | tests | plan | prepare | preflight | records | units | start WORKERS | status
set -euo pipefail
W=$HOME/work; PY=$W/venv/bin/python; SRC=$W/sdb-gen71x; S=$W/gen71
COMMIT=a588e09e4aec88fa8b41e814df95b515f07e134c
LIST=$S/all-training-families.json; LISTSHA=4818856d731bee23ea38cf16b478a73106ad06a2116dca046fae8a9098b103e3
. "$S/gen71e.env"      # BOX, OLD (the drained cohort whose unplayed deals this one takes over)
RUN=$W/runs/gen71-mix2-$BOX; PUB=$W/publication/gen71-mix2-$BOX; BRANCH=arena-gen7-1-mix2-$BOX-feed
PLAN=$S/plan-mix.json
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
assert '71s-32~7s-32' in p['pair_weights'], p['pair_weights']
p['roster'] = ['71s-32', '7s-32']
p['pair_weights'] = {'71s-32~71s-32': 1, '71s-32~7s-32': 1}
p['title'] = f'Gen 7.1 · standard self-play, and standard with policy v4.1 against Gen 7 standard, deals v4.1 was not trained on, on {box}'
p['interpretation'] = ('Gen 7.1 self-play supplies training data only (one table a deal, no IMP comparison); Gen 7.1 against Gen 7 is the same bot with '
                       'policy net v4.1 against itself with v4, so its result is what the new net is worth in play.')
p['notes'] = list(p.get('notes', [])) + [
    "This copy of configs/round71-compare.json plays 71s-32~71s-32 and 71s-32~7s-32, one board in two each, in place of its pairs: Max, 12 November 2026, "
    "11:36 UTC, of azure1 and azure4: \"Yes yes those two boxes for gen 7.1 self play and 7.1 vs 7\". The rule for opening configs/round71-selfplay.json "
    "(1,000 boards and a 95% lead for 7.1) was not met (07:53 UTC: 1,124 boards, -0.072 IMPs a board, 95% interval -0.222 to +0.078); this self-play is "
    "Max's instruction for these two machines and does not open that plan. Only the roster, the pair weights, the title, the interpretation and these notes differ.",
    "The cohort is prepared with --exclude-families: no deal from the 32,205 families the policy net v4.1 was trained on (the independent collector's "
    "all-training-families.json, sha256 4818856d731bee23...)."]
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
  for pattern in "test_gen71*.py" "test_gen7_selfplay.py"; do
    out=$(env $CAPS "$PY" -m unittest discover -s tests -p "$pattern" 2>&1 | grep -E "^(Ran|OK|FAILED|ERROR:|FAIL:)" | tr '\n' ' ' | cut -c1-600) || true
    say "tests $pattern: $out"
    case "$out" in *" OK"*) ;; *) bad=1 ;; esac
  done
  say "tests took $(( $(date +%s) - start ))s"
  [ -z "$bad" ] || { say "the Gen 7.1 or self-play tests did not pass"; exit 1; }
}

cmd_prepare() {
  [ "$(git -C "$SRC" rev-parse HEAD)" = "$COMMIT" ] || { say "source is not at $COMMIT"; exit 1; }
  [ -e "$RUN" ] && { say "$RUN already exists; not overwriting"; exit 1; }
  [ -e "$PUB" ] && { say "$PUB already exists; not overwriting"; exit 1; }
  if GIT_SSH_COMMAND="$SSH" git ls-remote --exit-code --heads "$REMOTE" "$BRANCH" >/dev/null 2>&1; then say "branch $BRANCH already exists on GitHub"; exit 1; fi
  # The source run is a Gen 7 cohort of this box. It has to be finished: stopped, collectors gone, records published.
  [ -e "$OLD/STOP" ] || { say "$OLD has no STOP file"; exit 1; }
  [ "$(sha256sum "$LIST" | cut -c1-64)" = "$LISTSHA" ] || { say "the list of training families is not the expected file"; exit 1; }
  for unit in arena-gen7 arena-gen71; do
    [ "$(systemctl is-active $unit 2>/dev/null)" = active ] && { say "the collector $unit is still running"; exit 1; }
  done
  [ -z "$(ls "$OLD/failures" 2>/dev/null)" ] || { say "the source cohort has failure records"; exit 1; }
  local played published
  played=$(ls "$OLD/receipts" | wc -l)
  published=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$OLD/publisher-status.json")
  [ "$played" = "$published" ] || { say "the source cohort has published $published of $played boards; publish the rest first"; exit 1; }
  [ -e "$OLD/WATCHDOG_STOP" ] || echo "Finished for good on 12 November 2026 at 03:50 UTC (the box went to Gen 8 work). On $(date -u +%FT%TZ) its unplayed deals not from the families the policy net v4.1 was trained on went to $(basename "$RUN"). No watchdog ran on this box." > "$OLD/WATCHDOG_STOP"
  cd "$SRC"
  "$PY" ops/prepare_gen7_alpha.py --source "$OLD" --run "$RUN" --plan "$PLAN" --exclude-families "$LIST" > "$S/prepare-mix.json"
  "$PY" - "$S/prepare-mix.json" "$OLD" "$RUN" "$played" "$LIST" "$LISTSHA" <<'PYEOF'
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
tree = d['gen7']['71s-32']['tree'][0]
assert d['gen7']['71s-32'] == d['gen7']['7s-32'], 'the two bots differ in more than the net'
assert d['allocation'] == {'71s-32~71s-32': 1, '71s-32~7s-32': 1}, d['allocation']
assert (tree['root_margin'], tree['trust'], tree['path'], tree['tricks']) == (0.25, 0.3, 0.5, 3), 'not the authorized tree settings'
assert m['bots']['7s-32'] == old['bots']['7s-32'], '7s-32 is not the phase 1 bot'
a, b = m['bots']['7s-32'], m['bots']['71s-32']
assert {k for k in a if a[k] != b.get(k)} == {'id', 'identity', 'gen7_policy', 'artifact_sha256'}, 'the two bots differ in more than the net'
assert b['artifact_sha256']['gen7_policy'] == 'cb3fcfd5c55873735ee22ea5e7ba04606794bed38d261fdf3f1b3a4af5c9fbed' and b['gen7_policy'].endswith('gen7_policy_v41.npz')
assert m['target'] == old['target'] - played - left_out == len(new_fams) and m['source_generation'] == old['identity'] and m['source_completed'] == played
assert b['identity'].startswith('7b0f58b4c403'), '71s-32 is not the bot the other Azure 7.1 cohorts play'
print(f"cohort {d['identity'][:12]}: {d['target']} deals taken over from cohort {old['identity'][:12]} ({played} of its {old['target']} were played, {left_out} unplayed deals from training families left out); pairs {d['allocation']}; "
      f"7s-32 identity {m['bots']['7s-32']['identity'][:12]} as in phase 1; 71s-32 identity {b['identity'][:12]}, differing from 7s-32 in the policy release only; audit {m['audit']}; gap forks {m.get('gap_fork')}; "
      f"exclusions {ex['families']} families, sha256 {ex['sha256'][:16]}; bidding conditions {m.get('bidding_conditions')}")
PYEOF
}

cmd_preflight() {
  cd "$SRC"; local start; start=$(date +%s)
  if ! env $CAPS "$PY" ops/smoke_gen7.py --run "$RUN" --out "$RUN/preflight.json" --deals 2 > "$S/preflight-mix.log" 2>&1; then
    say "preflight FAILED"; grep -v -E "absl|oneDNN|cpu_feature|AVX|^WARNING" "$S/preflight-mix.log" | tail -14 | cut -c1-300; exit 1
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
    source_repository='https://github.com/maxschireson/Single-Dummy-Bridge', source_branch='codex/gen71-independent-20261112 (feature/gen7-selfplay-20261112 at 9f5ec19 plus the option --exclude-families; engine, runtime and publisher unchanged)', source_commit=commit, generation='Gen 7.1: 71s-32 is 7s-32 with policy net v4.1; self-play and against Gen 7.0',
    source_run=f"shard 5/8 of the capture capsule's unplayed deals (cohort {old}, prepared for the claim and never played), without the families the policy net v4.1 was trained on (artifacts/validation/evaluation-exclusions.json)",
    capture='tie audits, tree audits, gap forks and the guess-size fields (this source has the capture port merged)',
    plan='configs/round71-compare.json with the pairs 71s-32~71s-32 and 71s-32~7s-32 (plan.json beside this file)', memory='unit gen71-recycle restarts the collector after the boards in hand when the box has under 5 GB of memory available', threads='one BLAS, OpenMP and TensorFlow thread a worker',
    publication_branch=branch, supervision='systemd units arena-gen71 and arena-gen71-publish; no BEN pair in this cohort',
    operator='Claude session https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ, through the boxctl agent (docs/boxctl.md)'),
    open(os.path.join(run, 'environment.json'), 'w'), indent=1)
json.dump(dict(launched_epoch=time.time(),
    authority="Max, 12 November 2026, 05:42 UTC: push 7.1 from 06:00 UTC unless revoked; replace the 7.0 self play with 7.0/7.1 matches for at least 1000 boards / until 7.1 establishes a 95% CI lead. 05:54 UTC: 'We can switch azure 2 to 100% 7.1 vs 7.0; 7 is clearly a big step vs 6.'",
    notice='docs/gen71_2026-11-12.md on feature/gen7-selfplay-20261112', host=box,
    reason="Max, 11:36 UTC: 'Yes yes those two boxes for gen 7.1 self play and 7.1 vs 7'",
    steps='prepare from the drained cohort with --exclude-families, preflight with ops/smoke_gen7.py, then the collector under systemd'),
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
Description=Gen 7.1 collector: self-play and against 7.0, deals v4.1 was not trained on
StartLimitIntervalSec=900
StartLimitBurst=3

[Service]
User=$U
WorkingDirectory=$SRC
EnvironmentFile=$S/workers.env
Environment=HOME=$HOME PYTHONUNBUFFERED=1 $CAPS
ExecStart=$PY -u ops/gen5_runtime.py --run $RUN --workers \${WORKERS}
StandardOutput=append:$S/collector-mix.log
StandardError=append:$S/collector-mix.log
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
UNIT
  sudo tee /etc/systemd/system/arena-gen71-publish.service >/dev/null <<UNIT
[Unit]
Description=Gen 7.1 self-play and against 7.0 feed publisher
After=network-online.target
Wants=network-online.target

[Service]
User=$U
WorkingDirectory=$SRC
Environment=HOME=$HOME PYTHONUNBUFFERED=1 $CAPS
ExecStart=$PY -u ops/publish_gen5.py --run $RUN --publication $PUB
StandardOutput=append:$S/publisher-mix.log
StandardError=append:$S/publisher-mix.log
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
  [ -z "$(ls "$RUN/failures")" ] || { for f in "$RUN"/failures/*.json; do cut -c1-600 "$f"; echo; done; tail -5 "$S/collector-mix.log" | cut -c1-300; exit 1; }
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
EOF_GEN71E
cat > "$S/go71e.sh" <<'EOF_GO71E'
#!/usr/bin/env bash
# azure1's next pool (its current cohort f37d8d826522 ends about 14:20 UTC): shard 5/8 of the capture capsule's unplayed deals
# (claimed on the board; shards 0 to 3 are the Azure phase 1 boxes', 4 the cloud collector's), without the v4.1 training
# families. Two steps, because --shard applied after --exclude-families would cut a different slice than the one the other
# shards use: cohort gen71-claim5 is shard 5/8 of the capsule exactly as the phase 1 shards were cut (never played), and
# cohort gen71-mix2 takes its deals without the training families. Prepared and preflighted while the current cohort plays;
# unit mixswitch moves the collector over when the current cohort has played all its deals.
set -uo pipefail
W=$HOME/work; S=$W/gen71; PY=$W/venv/bin/python; SRC=$W/sdb-gen71x
BOX=azure1; CAP=$W/capsule-gen7-capture/recovery; A=$W/runs/gen71-claim5-$BOX; B=$W/runs/gen71-mix2-$BOX
LIST=$S/all-training-families.json; PLAN=$S/plan-mix.json
say() { echo "$(date -u +%T) $*"; }
[ "$(sha256sum "$LIST" | cut -c1-64)" = 4818856d731bee23ea38cf16b478a73106ad06a2116dca046fae8a9098b103e3 ] || { say "the list of training families is not the expected file"; exit 1; }
[ "$(git -C "$SRC" rev-parse HEAD)" = a588e09e4aec88fa8b41e814df95b515f07e134c ] || { say "source is not at a588e09"; exit 1; }
[ -e "$B" ] && { say "$B already exists"; exit 1; }
cd "$SRC"
if [ ! -e "$A" ]; then
  "$PY" ops/prepare_gen7_alpha.py --source "$CAP" --run "$A" --plan "$PLAN" --shard 5/8 > "$S/prepare-claim5.json" || { say "prepare of the claim cohort failed"; exit 1; }
fi
touch "$A/STOP"
[ -e "$A/WATCHDOG_STOP" ] || echo "Never played. Prepared on $(date -u +%FT%TZ) to cut shard 5/8 of the capture capsule's unplayed deals exactly as the phase 1 shards were cut; its deals not from the families the policy net v4.1 was trained on went to $(basename "$B")." > "$A/WATCHDOG_STOP"
"$PY" ops/prepare_gen7_alpha.py --source "$A" --run "$B" --plan "$PLAN" --exclude-families "$LIST" > "$S/prepare-mix2.json" || { say "prepare of the mix2 cohort failed"; exit 1; }
"$PY" - "$CAP" "$A" "$B" "$LIST" <<'PYEOF' || exit 1
import glob, json, os, sys
sys.path.insert(0, os.getcwd())
from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load
cap, a, b, lst = sys.argv[1:5]
trained = set(json.load(open(lst)))
fam = lambda run: [deal_key(x.hands, True) for x in load(os.path.join(run, json.load(open(run + '/manifest.json'))['corpus']))]
mc = json.load(open(cap + '/manifest.json')); ma = json.load(open(a + '/manifest.json')); mb = json.load(open(b + '/manifest.json'))
cf = fam(cap); done = {json.load(open(p))['index'] for p in glob.glob(cap + '/receipts/*.json')}
U = [cf[i] for i in range(mc['target']) if i not in done]
af, bf = fam(a), fam(b)
assert af == U[5::8], 'the claim cohort is not shard 5/8 of the capsule'
for k in range(5): assert not set(af) & set(U[k::8]), k
assert bf == [f for f in af if f not in trained] and not set(bf) & trained
mine = set(fam(os.path.expanduser('~/work/runs/gen71-mix-azure1')))
assert not set(bf) & mine
assert mb['bots']['71s-32']['identity'].startswith('7b0f58b4c403') and mb['bots']['7s-32']['identity'].startswith('f0a578598673'), (mb['bots']['71s-32']['identity'][:12], mb['bots']['7s-32']['identity'][:12])
assert mb['pair_weights'] == {'71s-32~71s-32': 1, '71s-32~7s-32': 1} and mb['evaluation_exclusions']['sha256'] == '4818856d731bee23ea38cf16b478a73106ad06a2116dca046fae8a9098b103e3'
print(f"claim cohort {ma['identity'][:12]}: shard 5/8 of capsule {mc['identity'][:12]}, {len(af)} deals, disjoint from shards 0 to 4; mix2 cohort {mb['identity'][:12]}: {len(bf)} deals ({len(af) - len(bf)} training families left out), none in the current cohort")
PYEOF
printf 'BOX=%s\nOLD=%s\n' "$BOX" "$A" > "$S/gen71e.env"
for step in preflight records; do
  say "== $step"
  nice -n 5 bash "$S/gen71e.sh" $step || { say "STOPPED at: $step"; exit 1; }
done
sudo tee /etc/systemd/system/mixswitch.service >/dev/null <<UNIT
[Unit]
Description=Move azure1's Gen 7.1 collector to its next cohort when the current one has played all its deals

[Service]
User=$(id -un)
Environment=HOME=$HOME
ExecStart=$S/mixswitch.sh
StandardOutput=append:$S/mixswitch.log
StandardError=append:$S/mixswitch.log
Restart=on-failure
RestartSec=30
UNIT
sudo systemctl daemon-reload; sudo systemctl start mixswitch
say "next cohort armed: $(basename "$B"); mixswitch $(systemctl is-active mixswitch)"
say DONE
EOF_GO71E
cat > "$S/mixswitch.sh" <<'EOF_MIXSWITCH'
#!/usr/bin/env bash
# Unit mixswitch (azure1): when the cohort under arena-gen71 has played all its deals (collector exited, every board published),
# finish it, point the units at gen71-mix2 and start it with eight workers; then exit. ~/work/gen71/SWITCH_OFF switches it off.
set -uo pipefail
W=$HOME/work; S=$W/gen71; PY=$W/venv/bin/python; B=$W/runs/gen71-mix2-azure1
say() { echo "$(date -u +%FT%TZ) $*"; }
say "started"
while true; do
  sleep 60
  [ -e "$S/SWITCH_OFF" ] && continue
  R=$(systemctl show -p ExecStart --value arena-gen71 | sed -n 's/.*--run \([^ ;]*\).*/\1/p' | head -1)
  [ "$R" = "$B" ] && { say "already on $(basename "$B")"; exit 0; }
  [ "$(systemctl is-active arena-gen71)" = active ] && continue
  [ -e "$S/recycling" ] && continue
  t=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['target'])" "$R/manifest.json"); k=$(ls "$R/receipts" | wc -l)
  [ "$k" -ge "$t" ] || continue
  [ -z "$(ls "$R/failures")" ] || { say "failure record in $(basename "$R"); not switching"; continue; }
  p=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$R/publisher-status.json" 2>/dev/null)
  [ "$p" = "$k" ] || continue
  say "$(basename "$R") done: $k of $t boards, all published; moving to $(basename "$B")"
  touch "$S/RECYCLE_OFF" "$R/STOP" "$R/PUBLISH_STOP"
  for i in $(seq 1 30); do [ "$(systemctl is-active arena-gen71-publish)" = active ] || break; sleep 5; done
  sudo systemctl stop arena-gen71-publish >/dev/null 2>&1
  [ -e "$R/WATCHDOG_STOP" ] || echo "Finished on $(date -u +%FT%TZ): every deal played and published; the box went on with $(basename "$B"). No watchdog ran on this box." > "$R/WATCHDOG_STOP"
  if [ -L "$R/dds-cache.sqlite" ]; then T=$(readlink "$R/dds-cache.sqlite"); case "$T" in /mnt/ddscache/*) rm -f "$T" "$T-wal" "$T-shm";; esac; fi
  bash "$S/gen71e.sh" units && bash "$S/gen71e.sh" start 8
  rm -f "$S/RECYCLE_OFF"
  say "collector $(systemctl is-active arena-gen71), publisher $(systemctl is-active arena-gen71-publish) on $(basename "$B")"
  exit 0
done
EOF_MIXSWITCH
chmod +x "$S/gen71e.sh" "$S/go71e.sh" "$S/mixswitch.sh"
systemctl is-active --quiet go71e && { echo "already running"; exit 0; }
sudo systemctl reset-failed go71e 2>/dev/null || true
sudo systemd-run --quiet --unit=go71e --uid="$(id -un)" --setenv=HOME="$HOME" \
  --property=StandardOutput=append:"$S/go71e.log" --property=StandardError=append:"$S/go71e.log" -- "$S/go71e.sh"
sleep 45; echo "go71e: $(systemctl is-active go71e)"; tail -5 "$S/go71e.log" | cut -c1-330
