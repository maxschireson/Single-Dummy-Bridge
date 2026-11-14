# boxctl: timeout=300
# boxctl: timeout=300
# loop session (Max, 04:30 UTC on 14 November: "We should run more Ben compare deals"): BEN is installed on azure2 as azure3 has
# it (ben_install.sh from 2d760db, read from the second checkout so the matches' source is untouched), at Nice 10 in a unit
# of its own beside the box's matches. No cost: the box is one already rented. Returns at once; the log is ~/work/loop/ben/install.log.
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc
[ -d "$S2/.git" ] || git clone -q --depth 5 --branch research/rollout-loop-20261113 https://github.com/maxschireson/Single-Dummy-Bridge "$S2"
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q 2d760dbdfe2a59ff2b3416a492339133072b3ab4
ls -d "$HOME/work/ben" "$HOME/work/ben-venv" "$HOME/work/lanes" 2>/dev/null || echo "no BEN here yet"
df -h --output=avail "$HOME" | tail -1; python3 --version; python3 -c "import venv, ensurepip; print('venv ok')" 2>&1 | tail -1
sudo systemctl reset-failed loop-beninstall 2>/dev/null || true
sudo systemd-run --unit=loop-beninstall --uid="$USER" --working-directory="$S2" --setenv=HOME="$HOME" --property=Nice=10 -- bash "$S2/training/rollout-loop-20261113/ben_install.sh"
sleep 20; systemctl is-active loop-beninstall || true; tail -n 3 "$W/ben/install.log" 2>/dev/null; tail -n 1 "$W/runs.log" | cut -c1-150; date -u +%FT%TZ
