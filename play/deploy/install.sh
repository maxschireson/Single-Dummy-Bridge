#!/usr/bin/env bash
# Install or update the Sid play server on an Ubuntu box (run as a user with passwordless sudo, e.g. through boxctl).
#
#   bash install.sh APP_COMMIT SOURCE_COMMIT [RECIPE]
#
#   APP_COMMIT     full sha of the commit carrying play/ (this server)
#   SOURCE_COMMIT  full sha of the source the bot was frozen with (the recipe's provenance.source_commit; stu4c-put, stu4-put:
#                  a42fe6c1f9f66c17a8889e66a9d2542b60b32646, 8s-32: 792c4cb3f647ec71273f0cc57d95be1d0a0a5954)
#   RECIPE         bot recipe under play/bundles/ (default stu4c-put.json)
#
# Layout: /opt/sidplay/{app-<sha>,source-<sha>,bundles/<bot>-<sha>,venv} owned by root; symlinks app, source, bundle;
# data in /var/lib/sidplay owned by the unprivileged `sidplay` user, which runs the service. Listens on 127.0.0.1:8090
# only. Re-running with new commits installs alongside and switches the symlinks; the old versions stay for rollback.
# Exposure to the internet is a separate step (expose.sh, then caddy.sh).
set -euo pipefail
APP_COMMIT=${1:?app commit}
SOURCE_COMMIT=${2:?source commit}
RECIPE=${3:-stu4c-put.json}
REPO=https://github.com/maxschireson/Single-Dummy-Bridge.git
ROOT=/opt/sidplay
PY=python3

fetch() {   # fetch <sha> <dir>: one commit, no history
  local sha=$1 dir=$2
  if [ -d "$dir/.git" ] && [ "$(git -C "$dir" rev-parse HEAD 2>/dev/null)" = "$sha" ]; then return; fi
  sudo rm -rf "$dir.tmp"
  sudo mkdir -p "$dir.tmp" && sudo chown "$USER" "$dir.tmp"
  git -C "$dir.tmp" init -q
  git -C "$dir.tmp" remote add origin "$REPO"
  git -C "$dir.tmp" fetch -q --depth 1 origin "$sha"
  git -C "$dir.tmp" checkout -q FETCH_HEAD
  sudo rm -rf "$dir"
  sudo mv "$dir.tmp" "$dir"
}

echo "== user and directories"
id sidplay >/dev/null 2>&1 || sudo useradd --system --home-dir /var/lib/sidplay --create-home --shell /usr/sbin/nologin sidplay
sudo mkdir -p "$ROOT/bundles" /var/lib/sidplay
sudo chown -R "$USER" "$ROOT"          # back to root at the end
sudo chown sidplay:sidplay /var/lib/sidplay
sudo chmod 750 /var/lib/sidplay

echo "== code"
fetch "$APP_COMMIT" "$ROOT/app-$APP_COMMIT"
fetch "$SOURCE_COMMIT" "$ROOT/source-$SOURCE_COMMIT"

echo "== sure-trick search (play/native/sure.cpp, for the analyses)"
if [ ! -x "$ROOT/app-$APP_COMMIT/play/native/sure_cpp" ]; then
  command -v g++ >/dev/null || sudo apt-get install -y -q g++
  (cd "$ROOT/app-$APP_COMMIT/play/native" && { g++ -O2 -march=native -std=c++17 -o sure_cpp sure.cpp || g++ -O2 -std=c++17 -o sure_cpp sure.cpp; })
fi

echo "== python environment"
if [ ! -x "$ROOT/venv/bin/python" ]; then $PY -m venv "$ROOT/venv"; fi
"$ROOT/venv/bin/pip" install -q --upgrade pip
"$ROOT/venv/bin/pip" install -q -r "$ROOT/app-$APP_COMMIT/play/requirements.txt"

echo "== double-dummy solver"
if [ ! -f "$ROOT/source-$SOURCE_COMMIT/bridge_harness/libbridge_dds.so" ]; then
  (cd "$ROOT/source-$SOURCE_COMMIT" && "$ROOT/venv/bin/python" scripts/build_dds.py)
fi

echo "== bundle"
BOT=$(basename "$RECIPE" .json)
RECIPE_SHA=$(sha256sum "$ROOT/app-$APP_COMMIT/play/bundles/$RECIPE" | cut -c1-12)
BUNDLE="$ROOT/bundles/$BOT-$SOURCE_COMMIT-$RECIPE_SHA"
if [ ! -f "$BUNDLE/bundle.json" ]; then
  rm -rf "$BUNDLE"
  "$ROOT/venv/bin/python" "$ROOT/app-$APP_COMMIT/play/bundle.py" from-models \
    --recipe "$ROOT/app-$APP_COMMIT/play/bundles/$RECIPE" --source "$ROOT/source-$SOURCE_COMMIT" --out "$BUNDLE" --restore
fi

echo "== switch"
sudo ln -sfn "$ROOT/app-$APP_COMMIT" "$ROOT/app"
sudo ln -sfn "$ROOT/source-$SOURCE_COMMIT" "$ROOT/source"
sudo ln -sfn "$BUNDLE" "$ROOT/bundle"
sudo chown -R root:root "$ROOT"
sudo chmod -R go-w "$ROOT"
if [ ! -f /etc/sidplay.env ]; then
  sudo install -m 644 "$ROOT/app/play/deploy/sidplay.env" /etc/sidplay.env
fi
sudo install -m 644 "$ROOT/app/play/deploy/sidplay.service" /etc/systemd/system/sidplay.service
sudo systemctl daemon-reload
sudo systemctl enable sidplay >/dev/null 2>&1
sudo systemctl restart sidplay

echo "== health"
for i in $(seq 1 60); do
  if curl -fsS --noproxy '*' http://127.0.0.1:8090/api/health 2>/dev/null; then echo; exit 0; fi
  sleep 5
done
echo "sidplay did not become healthy"; sudo journalctl -u sidplay -n 60 --no-pager; exit 1
