# boxctl: timeout=300
# loop session: azure5 serves the pool's row files (~/work/plan/rnet2w/data: train.npz, freshB.npz) to azure7 over the private
# network for 60 minutes (a unit, loop-serve, bound to the private address only; it stops itself), and computes their sha256
# so azure7 can check its copy. Read-only.
set -uo pipefail
D=$HOME/work/plan/rnet2w/data; IP=$(hostname -I | awk '{print $1}')
sudo systemctl stop loop-serve 2>/dev/null; sudo systemctl reset-failed loop-serve 2>/dev/null
sudo systemd-run --unit=loop-serve --uid="$USER" --working-directory="$D" --property=RuntimeMaxSec=3600 -- /usr/bin/python3 -m http.server 8765 --bind "$IP" --directory "$D"
sleep 2; systemctl is-active loop-serve
nice -n 19 sha256sum "$D/train.npz" "$D/freshB.npz" | sed "s#$D/##"
date -u +%T
