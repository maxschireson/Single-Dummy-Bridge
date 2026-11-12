# boxctl: timeout=120
# p41: fetch the two new scripts into place (no running script is touched) and arm the scoring of each five-epoch run.
set -uo pipefail
P=$HOME/work/p41; cd ~/work/p41src; D=training/policy-v4.1-20261112
git fetch -q --depth 1 origin transfer/gen7-policy-v4.1-20261112
for f in push_all.sh eval_more.sh; do git show FETCH_HEAD:$D/$f > $D/$f; chmod +x $D/$f; done
sudo systemd-run --unit=p41-eval-w512e5 --uid="$(id -un)" --working-directory="$P" --setenv=HOME="$HOME" -- /bin/bash $HOME/work/p41src/$D/eval_more.sh E w512e5 2>&1 | tail -1
sudo systemd-run --unit=p41-eval-w768e5 --uid="$(id -un)" --working-directory="$P" --setenv=HOME="$HOME" -- /bin/bash $HOME/work/p41src/$D/eval_more.sh F w768e5 2>&1 | tail -1
systemctl is-active p41-w512e5 p41-w768e5 p41-eval-w512e5 p41-eval-w768e5 p41-inf-v4-0 p41-inf-v41-0 p41-inf-v4-1 p41-inf-v41-1 | tr '\n' ' '; echo
tail -n +2 $P/logs/w512e5.out | cut -c1-330; tail -1 $P/logs/w512e5.err; cat $P/logs/w768e5.out | cut -c1-330; tail -1 $P/logs/w768e5.err; date -u +%T
