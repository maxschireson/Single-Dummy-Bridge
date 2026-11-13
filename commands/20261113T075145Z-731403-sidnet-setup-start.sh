# boxctl: timeout=1800
# boxctl: timeout=1800
# sidnet: set up ~/work/sidnet (source, solvers, scorer, v2 net) and start the label chain as unit sidnet-run.
set -euo pipefail
mkdir -p ~/work/sidnet && cd ~/work/sidnet
curl -fsSL https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/aa187281edc380158bb28d0a3d9163d0444663fe/training/sid-net-s0-20261113/box-setup.sh -o box-setup.sh
bash box-setup.sh research/sid-net-s0-20261113
if systemctl is-active --quiet sidnet-run; then echo "sidnet-run is already running"; else
  sudo systemd-run --unit=sidnet-run --uid="$USER" --working-directory="$HOME/work/sidnet/src" --setenv=HOME="$HOME" \
    --property=Nice=10 --setenv=STAGES="fetch label fetchB labelB" -- bash training/sid-net-s0-20261113/chain.sh
fi
sleep 45
systemctl status sidnet-run --no-pager 2>&1 | sed -n 1,6p
cat ~/work/sidnet/logs/timeline.log; tail -2 ~/work/sidnet/logs/fetch.log 2>/dev/null | cut -c1-200
