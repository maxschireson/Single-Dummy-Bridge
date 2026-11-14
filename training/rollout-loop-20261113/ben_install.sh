#!/usr/bin/env bash
# BEN on a box that does not have the arena's lanes, laid out as on azure3 so that ben_session.sh and ben.sh run there
# unchanged:  ben_install.sh
#   ~/work/ben        lorserker/ben at the commit in ben/manifest.json
#   ~/work/ben-venv   Python packages pinned in ben/requirements.txt (azure3's pip freeze)
#   ~/work/lanes/N.env  BEN_CONF (a copy of azure3's lane config, ben/ben-64-lane.conf) and BEN_PORT, lanes 1 to 8
# It checks the checkout's tree hash, the model files' hashes, the config's hash and the installed packages against
# azure3's (ben/manifest.json, ben/files.sha256) and says PASS or FAIL. Network namespaces are made by ben_session.sh.
# Nothing here costs money: the box is one we already rent. Does nothing on a box that already has ~/work/ben.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); B=$HERE/ben; W=$HOME/work; L=$W/loop/ben; mkdir -p "$L" "$W/lanes"
say() { echo "$(date -u +%FT%TZ) $*" | tee -a "$L/install.log"; }
get() { python3 -c "import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])" "$B/manifest.json" "$1"; }
COMMIT=$(get commit)
if [ ! -d "$W/ben/.git" ]; then
  say "fetching lorserker/ben at ${COMMIT:0:7}"
  git init -q "$W/ben" && git -C "$W/ben" remote add origin "$(get repository)"
  git -C "$W/ben" fetch -q --depth 1 origin "$COMMIT" || { say "fetch by commit failed; cloning"; rm -rf "$W/ben"; git clone -q "$(get repository)" "$W/ben"; }
  git -C "$W/ben" checkout -q "$COMMIT" 2>/dev/null || git -C "$W/ben" checkout -q FETCH_HEAD
fi
[ "$(git -C "$W/ben" rev-parse HEAD)" = "$COMMIT" ] || { say "FAIL: ~/work/ben is at $(git -C "$W/ben" rev-parse --short HEAD)"; exit 1; }
if [ ! -x "$W/ben-venv/bin/python" ]; then
  say "building ~/work/ben-venv"
  python3 -m venv "$W/ben-venv" && "$W/ben-venv/bin/pip" install -q --upgrade pip >/dev/null 2>&1
  "$W/ben-venv/bin/pip" install -q -r "$B/requirements.txt" >> "$L/install.log" 2>&1 || { say "FAIL: pip install"; exit 1; }
fi
mkdir -p "$W/benconf" && cp -f "$B/ben-64-lane.conf" "$W/benconf/ben-64.conf"
for n in 1 2 3 4 5 6 7 8; do
  [ -e "$W/lanes/$n.env" ] || printf 'BEN_PORT=8089\nBEN_CONF=%s\n' "$W/benconf/ben-64.conf" > "$W/lanes/$n.env"
done
ok=1
tree=$(cd "$W/ben" && git ls-files -z src bin models/TF2models | xargs -0 sha256sum | sha256sum | cut -c1-64)
[ "$tree" = "$(get tree_sha256)" ] && say "tree hash matches azure3's" || { say "FAIL: tree hash $tree"; ok=0; }
(cd "$W/ben" && sha256sum --quiet -c "$B/files.sha256") && say "the 16 models and libdds.so match azure3's" || { say "FAIL: model files differ"; ok=0; }
[ "$(sha256sum "$W/benconf/ben-64.conf" | cut -c1-64)" = "$(get lane_config_sha256)" ] && say "config matches azure3's lane config" || { say "FAIL: config"; ok=0; }
freeze=$("$W/ben-venv/bin/pip" freeze 2>/dev/null | sort | sha256sum | cut -c1-64)
[ "$freeze" = "$(get pip_freeze_sorted_sha256)" ] && say "installed packages match azure3's" || { say "FAIL: packages differ ($freeze)"; "$W/ben-venv/bin/pip" freeze | sort | diff - <(sort "$B/requirements.txt") | head -20 | tee -a "$L/install.log"; ok=0; }
say "python $("$W/ben-venv/bin/python" --version 2>&1) (azure3: $(get python)); disk free $(df -h --output=avail "$HOME" | tail -1)"
[ "$ok" = 1 ] && say "BEN install: PASS" || { say "BEN install: FAIL"; exit 1; }
