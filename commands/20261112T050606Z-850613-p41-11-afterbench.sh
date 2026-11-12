# boxctl: timeout=120
# p41: fetch the one new script without touching the checkout's other files (several of them are running), arm it, and show the 512-wide scoring.
set -uo pipefail
P=$HOME/work/p41; cd ~/work/p41src
git fetch -q --depth 1 origin transfer/gen7-policy-v4.1-20261112 && git show FETCH_HEAD:training/policy-v4.1-20261112/after_bench.sh > $P/after_bench.sh && chmod +x $P/after_bench.sh
sudo systemd-run --unit=p41-afterbench --uid="$(id -un)" --working-directory="$P" --setenv=HOME="$HOME" -- /bin/bash $P/after_bench.sh 2>&1 | tail -1
tail -5 $P/logs/timeline.log; tail -2 $P/logs/bench.log | cut -c1-200; tail -1 $P/logs/w768.err; echo "--- eval512 (from the epochs on)"; sed -n '/== epochs on fresh C/,$p' $P/logs/eval512.log | cut -c1-1200
