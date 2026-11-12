# boxctl: timeout=600
# p41: start the chain (build the training set in parts, held-out set B, train 512 wide, then set C and 768 wide)
# as unit p41-chain. It waits for the first fetch by itself.
set -euo pipefail
P=$HOME/work/p41
git -C ~/work/p41src pull -q --depth 1 origin transfer/gen7-policy-v4.1-20261112 2>&1 | tail -1
git -C ~/work/p41src log -1 --format='p41src %h %s' | cut -c1-120
sudo systemd-run --unit=p41-chain --uid="$(id -un)" --working-directory="$P" --setenv=HOME="$HOME" -- /bin/bash $HOME/work/p41src/training/policy-v4.1-20261112/chain.sh 2>&1 | tail -1
sleep 5; cat $P/logs/timeline.log; tail -2 $P/logs/fetch1.log; du -sh $P/eps | cut -f1; ls $P/eps | wc -l
