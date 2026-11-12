# boxctl: timeout=3000
# Box setup for the arena: build tools, source, run capsule, Python env.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
echo "== packages"
sudo apt-get update -qq
sudo apt-get install -y -qq build-essential python3-venv python3-dev >/dev/null
g++ --version | head -1
mkdir -p ~/work && cd ~/work
REPO=https://github.com/maxschireson/Single-Dummy-Bridge
echo "== source (Gen 7 candidate branch)"
[ -d sdb-gen7 ] || git clone -q --depth 1 --branch feature/gen7-candidate-20261111 "$REPO" sdb-gen7
git -C sdb-gen7 log -1 --format='%H %s'
echo "== capsule (arena-gen6-gen7-capture-feed)"
[ -d capsule-gen7-capture ] || git clone -q --depth 1 --branch arena-gen6-gen7-capture-feed "$REPO" capsule-gen7-capture
git -C capsule-gen7-capture log -1 --format='%H %s'
du -sh sdb-gen7 capsule-gen7-capture
echo "== python env"
[ -x venv/bin/python ] || python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q "tensorflow-cpu==2.21.0" scipy 2>&1 | tail -2 \
  || venv/bin/pip install -q "tensorflow==2.21.0" scipy 2>&1 | tail -2 \
  || venv/bin/pip install -q tensorflow scipy 2>&1 | tail -2
venv/bin/python -c "import tensorflow as tf, numpy, scipy; print('tensorflow', tf.__version__, '| numpy', numpy.__version__, '| scipy', scipy.__version__)"
