# boxctl: timeout=3000
# boxctl: timeout=3000
# g8: a fresh box for Gen 8 experiments. Build tools, the run capsule, a Python environment (no TensorFlow: the
# match runner reads the bidder with NumPy). The Gen 8 checkout, models and DDS come with the next command (g8-01-setup).
set -uo pipefail
export DEBIAN_FRONTEND=noninteractive
echo "== packages"
sudo apt-get update -qq
sudo apt-get install -y -qq build-essential python3-venv python3-dev git >/dev/null
g++ --version | head -1
mkdir -p ~/work && cd ~/work
REPO=https://github.com/maxschireson/Single-Dummy-Bridge
echo "== capsule (arena-gen6-gen7-capture-feed)"
[ -d capsule-gen7-capture ] || git clone -q --depth 1 --branch arena-gen6-gen7-capture-feed "$REPO" capsule-gen7-capture
git -C capsule-gen7-capture log -1 --format='%h %s' | cut -c1-100
du -sh capsule-gen7-capture | cut -f1
ls capsule-gen7-capture/recovery | head -8 | tr '\n' ' '; echo
echo "== python env"
[ -x venv/bin/python ] || python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q numpy scipy h5py 2>&1 | tail -2
venv/bin/python -c "import numpy, scipy, h5py, sys; print('python', sys.version.split()[0], '| numpy', numpy.__version__, '| scipy', scipy.__version__, '| h5py', h5py.__version__)"
nproc --all; free -g | sed -n 2p | awk '{print "memory GB:", $2}'; df -h ~ | sed -n 2p | awk '{print "disk free:", $4}'
