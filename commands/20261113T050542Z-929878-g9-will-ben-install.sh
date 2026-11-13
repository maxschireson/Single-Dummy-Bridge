# boxctl: timeout=3000
#!/bin/bash
# G9: install BEN on azure4 for the Gen 9 cohort's BEN pairs (g9, 13 Nov 05:06): G9-W7's install step.
# lorserker/ben at the pinned commit (configs/ben-gen5-16.provenance.json) in ~/work/g9/ben, its packages in
# ~/work/g9/ben-venv, every BEN 16 model checked against the provenance hashes. Starts no server.
set -euo pipefail
SRC=~/work/g9/ben-lanes-src
if [ ! -d "$SRC/.git" ]; then
  git clone -q --depth 1 --branch feature/gen9-workflow-ben-lanes https://github.com/maxschireson/Single-Dummy-Bridge "$SRC"
else
  git -C "$SRC" fetch -q --depth 1 origin feature/gen9-workflow-ben-lanes && git -C "$SRC" checkout -q FETCH_HEAD
fi
echo "lanes source $(git -C "$SRC" rev-parse --short HEAD)"
cd "$SRC"
start=$(date +%s)
nice -n 10 python3 ops/gen9_ben_lanes.py install --ben ~/work/g9/ben --venv ~/work/g9/ben-venv
echo "install took $(( $(date +%s) - start )) s"
du -sh ~/work/g9/ben ~/work/g9/ben-venv
~/work/g9/ben-venv/bin/python -c "import tensorflow as tf, numpy; print('tf', tf.__version__, 'numpy', numpy.__version__)"
for c in $(find ~/work/feeds ~/work/capsule-gen7-capture -maxdepth 4 -name "ben-*.conf" 2>/dev/null | xargs -r sha256sum | sort -u -k1,1 | cut -c67-); do
  echo "== $c"; grep -E '^\s*(\[|.*model|.*search|.*sample|use_bba|consult_bba)' "$c" | head -30
  grep -oE 'models/[^ ]+' "$c" | sort -u | while read -r m; do [ -e ~/work/g9/ben/$m ] && echo "  present $m" || echo "  MISSING $m"; done
done
sudo -n true && echo "passwordless sudo: yes" || echo "passwordless sudo: no"
systemctl --version | head -1
df -h ~ | tail -1
