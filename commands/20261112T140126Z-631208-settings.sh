# boxctl: timeout=60
# azure1 (Max, 13:52 and 13:56 UTC): pause the Gen 7.1 mix cohort and run fork-free settings matches (7.1 at layout-weight exponent
# 1.0 against 7.0 as deployed, and against 7.0 at 1.0). Background unit settings1; progress in ~/work/settings/settings1.log.
set -euo pipefail
X=$HOME/work/settings; mkdir -p "$X"
[ "$BOXCTL_BOX" = azure1 ] || { echo "this command is for azure1"; exit 1; }
cat > "$X/settings1.sh" <<'EOF_S1'
#!/usr/bin/env bash
# azure1, Max 13:52 UTC ("Can we explore the settings more deeply and see if we can restore even a small advantage from the better
# net?") and 13:56 ("Fine to pause the other activities on azure 1"). Pause the Gen 7.1 mix cohort (graceful drain, nothing deleted,
# its successor stays prepared and unstarted), then run fork-free matches with scripts/gen8_match.py (Gen 8 prototype branch at
# 48982f7; its engine additions are inert at their defaults) on fresh random deals, the same deals for every match:
#   M1  7.1 with layout-weight exponent 1.0  against  7.0 as deployed (0.5)     does a retuned 7.1 beat today's 7.0?
#   M3  7.1 with exponent 1.0                against  7.0 with exponent 1.0     is the better net worth anything at that setting?
# The 4.1 session's reading bench found exponent 1.0 best for every net (v4.1: +0.198 tricks a board against no reading at 1.0,
# +0.158 at 0.5, the deployed value).
set -uo pipefail
W=$HOME/work; S=$W/gen71; PY=$W/venv/bin/python; X=$W/settings; SRC=$W/sdb-g8p
COMMIT=48982f78fa08e1f4889681722d89c91f88ab1427
SSH="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
REMOTE=git@github.com:maxschireson/Single-Dummy-Bridge.git; BRANCH=transfer/gen71-settings-azure1-20261112
say() { echo "$(date -u +%T) $*"; }
mkdir -p "$X"
say "== pause the Gen 7.1 mix cohort"
touch "$S/SWITCH_OFF"; sudo systemctl stop mixswitch 2>/dev/null
touch "$S/RECYCLE_OFF"; for i in $(seq 1 120); do [ -e "$S/recycling" ] || break; sleep 5; done
sudo systemctl disable --now gen71-recycle >/dev/null 2>&1
R=$(systemctl show -p ExecStart --value arena-gen71 | sed -n 's/.*--run \([^ ;]*\).*/\1/p' | head -1)
touch "$R/STOP"
for i in $(seq 1 360); do [ "$(systemctl is-active arena-gen71)" = active ] || break; sleep 5; done
[ "$(systemctl is-active arena-gen71)" = active ] && { say "collector still running after 30 minutes"; exit 1; }
[ -z "$(ls "$R/failures")" ] || { say "failure record in $(basename "$R")"; exit 1; }
k=$(ls "$R/receipts" | wc -l)
for i in $(seq 1 90); do p=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$R/publisher-status.json" 2>/dev/null); [ "$p" = "$k" ] && break; sleep 10; done
[ "$p" = "$k" ] || { say "feed has $p of $k boards; publisher left running"; exit 1; }
touch "$R/PUBLISH_STOP"; for i in $(seq 1 30); do [ "$(systemctl is-active arena-gen71-publish)" = active ] || break; sleep 5; done
sudo systemctl disable --now arena-gen71-publish >/dev/null 2>&1; sudo systemctl disable arena-gen71 >/dev/null 2>&1
if [ -L "$R/dds-cache.sqlite" ]; then T=$(readlink "$R/dds-cache.sqlite"); case "$T" in /mnt/ddscache/*) rm -f "$T" "$T-wal" "$T-shm";; esac; fi
say "paused $(basename "$R") at $k of $("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['target'])" "$R/manifest.json") boards, all published; gen71-mix2-azure1 stays prepared"
say "== source"
if [ ! -d "$SRC/.git" ]; then git init -q "$SRC" && git -C "$SRC" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; fi
git -C "$SRC" fetch -q --depth 1 origin "$COMMIT" && git -C "$SRC" checkout -q FETCH_HEAD || { say "could not check out $COMMIT"; exit 1; }
cd "$SRC"
for r in models/cardplay/gen7-policy-v4-2026-11-11/restore*.py models/cardplay/gen7-policy-v4.1-2026-11-12/restore*.py; do
  [ -e "$r" ] && (cd "$(dirname "$r")" && "$PY" "$(basename "$r")" >/dev/null 2>&1)
done
"$PY" scripts/build_dds.py >/dev/null 2>&1 || true
[ -s bridge_harness/libbridge_dds.so ] || { say "DDS library was not built"; exit 1; }
say "checkout $(git rev-parse --short HEAD); v4 $(sha256sum models/cardplay/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz | cut -c1-16), v4.1 $(sha256sum models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz | cut -c1-16)"
"$PY" - configs/gen8-proto-bots.json "$X/bots.json" <<'PYEOF' || exit 1
import json, sys
from copy import deepcopy
d = json.load(open(sys.argv[1])); a, b = d['7s-32'], d['7s-32-v41']
assert {k for k in set(a) | set(b) if a.get(k) != b.get(k)} == {'label', 'gen7_policy'} and a['gen7']['play_weight'] == 0.5
out = {'7s-32': a, '71s-32': dict(b, label='Gen 7.1 standard (32), as deployed')}
for key, base, label in (('7s-32-w1', a, 'Gen 7 standard (32), layout-weight exponent 1.0'), ('71s-32-w1', b, 'Gen 7.1 standard (32), layout-weight exponent 1.0')):
    e = deepcopy(base); e['gen7']['play_weight'] = 1.0; e['label'] = label; out[key] = e
json.dump(out, open(sys.argv[2], 'w'), indent=1)
print('bots:', {k: (v['gen7_policy'].split('/')[-1], v['gen7']['play_weight']) for k, v in out.items()})
PYEOF
CAP=$W/capsule-gen7-capture/recovery
CAPS="OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1"
say "== smoke: two boards each"
for pair in 71s-32-w1~7s-32 71s-32-w1~7s-32-w1; do
  env $CAPS "$PY" -u scripts/gen8_match.py --source "$CAP" --bots "$X/bots.json" --pair "$pair" --deals 2 --first 900000 --seed 7111 --workers 2 --out "$X/smoke-${pair//\~/-v-}" > "$X/smoke.log" 2>&1 || { say "smoke FAILED for $pair"; tail -8 "$X/smoke.log" | cut -c1-300; exit 1; }
  say "smoke $pair: $(python3 -c "import json,sys; s=json.load(open(sys.argv[1])); print({k: s.get(k) for k in ('boards','cpu_per_board')})" "$X/smoke-${pair//\~/-v-}/summary.json")"
done
say "== matches"
for spec in "m1 71s-32-w1~7s-32" "m3 71s-32-w1~7s-32-w1"; do
  set -- $spec
  sudo systemctl reset-failed "match-$1" 2>/dev/null
  sudo systemd-run --quiet --unit="match-$1" --uid="$(id -un)" --setenv=HOME="$HOME" --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 --setenv=MKL_NUM_THREADS=1 \
    --working-directory="$SRC" --property=StandardOutput=append:"$X/$1.log" --property=StandardError=append:"$X/$1.log" -- \
    "$PY" -u scripts/gen8_match.py --source "$CAP" --bots "$X/bots.json" --pair "$2" --deals 3000 --seed 7111 --workers 4 --out "$X/$1"
  say "match-$1 ($2): $(systemctl is-active "match-$1")"
done
say "== results publisher"
P=$X/publication
if [ ! -d "$P/.git" ]; then
  mkdir -p "$P" && git -C "$P" init -q && git -C "$P" checkout -q --orphan "$BRANCH"
  git -C "$P" remote add origin "$REMOTE"; git -C "$P" config core.sshCommand "$SSH"
  git -C "$P" config user.name "Claude"; git -C "$P" config user.email "noreply@anthropic.com"
fi
cat > "$X/publish.sh" <<'PUB'
#!/usr/bin/env bash
X=$HOME/work/settings; P=$X/publication
while true; do
  for m in m1 m3; do mkdir -p "$P/$m"; for f in summary.json results.jsonl; do [ -e "$X/$m/$f" ] && cp "$X/$m/$f" "$P/$m/$f"; done; done
  cp "$X/bots.json" "$P/bots.json"; cp "$X/README.md" "$P/README.md" 2>/dev/null
  git -C "$P" add -A >/dev/null 2>&1
  if ! git -C "$P" diff --cached --quiet; then
    git -C "$P" commit -q -m "Gen 7.1 settings matches on azure1, $(date -u +%FT%TZ)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ"
    git -C "$P" push -q -f origin HEAD:refs/heads/transfer/gen71-settings-azure1-20261112 2>/dev/null
  fi
  sleep 600
done
PUB
chmod +x "$X/publish.sh"
cat > "$X/README.md" <<'MD'
# Gen 7.1 settings matches on azure1 (12 November 2026)

Max, 13:52 UTC: "Can we explore the settings more deeply and see if we can restore even a small advantage from the better net?"
Fork-free duplicate matches with `scripts/gen8_match.py` (branch `feature/gen8-prototype-20261112` at `48982f7`; its Gen 8
engine additions are inert at their defaults), on fresh random deals (seed 7111, indices 0 to 2,999, the same deals in both
matches), common and native bidding by the capsule's 6-32 bidder. Bots in `bots.json`: `7s-32` and `71s-32` exactly as the
Gen 8 session's `7s-32` and `7s-32-v41` (Gen 7 standard with policy v4 and v4.1); `-w1` is the same bot with the layout-weight
exponent `play_weight` 1.0 instead of 0.5. Results are from the first-named bot's side.

- `m1`: `71s-32-w1` against `7s-32`. Does a retuned 7.1 beat 7.0 as deployed?
- `m3`: `71s-32-w1` against `7s-32-w1`. Is the better net worth anything at exponent 1.0?

Why exponent 1.0: the 4.1 session's reading bench (`reports/gen8-reading-by-net-2026-11-12` on `feature/gen8-p41-20261112`)
found every net does best at 1.0 (v4.1: +0.198 tricks a board against no reading, +0.158 at 0.5).
Operator: Claude session https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ.
MD
sudo systemctl reset-failed settings-pub 2>/dev/null
sudo systemd-run --quiet --unit=settings-pub --uid="$(id -un)" --setenv=HOME="$HOME" --property=StandardOutput=append:"$X/publish.log" --property=StandardError=append:"$X/publish.log" -- "$X/publish.sh"
say "settings-pub $(systemctl is-active settings-pub); branch $BRANCH"
say DONE
EOF_S1
chmod +x "$X/settings1.sh"
systemctl is-active --quiet settings1 && { echo "already running"; exit 0; }
sudo systemctl reset-failed settings1 2>/dev/null || true
sudo systemd-run --quiet --unit=settings1 --uid="$(id -un)" --setenv=HOME="$HOME" \
  --property=StandardOutput=append:"$X/settings1.log" --property=StandardError=append:"$X/settings1.log" -- "$X/settings1.sh"
sleep 20; echo "settings1: $(systemctl is-active settings1)"; tail -4 "$X/settings1.log" | cut -c1-240
